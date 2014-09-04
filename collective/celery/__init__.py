"""
This is all pulled out of David Glick's gist on github
https://gist.githubusercontent.com/davisagli/5824662/raw/de6ac44c1992ead62d7d98be96ad1b55ed4884af/gistfile1.py  # noqa
"""

from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import noSecurityManager
from Testing.makerequest import makerequest
from ZODB.POSException import ConflictError
from celery import Task
from zope.app.publication.interfaces import BeforeTraverseEvent
from zope.component.hooks import setSite
from zope.event import notify
import transaction
import logging
from collective.celery.utils import getCelery, getApp
from OFS.interfaces import IItem
from plone import api
from Products.CMFPlone.interfaces.siteroot import IPloneSiteRoot


logger = logging.getLogger('collective.celery')


def initialize(context):
    pass


_object_marker = 'object://'


def _serialize_arg(val):
    if IItem.providedBy(val):
        val = '%s%s' % (
            _object_marker,
            '/'.join(val.getPhysicalPath()))
    return val


def _deserialize_arg(app, val):
    if isinstance(val, basestring):
        if val.startswith(_object_marker):
            val = val[len(_object_marker):]
            val = app.restrictedTraverse(val)
    return val


class AfterCommitTask(Task):
    """Base for tasks that queue themselves after commit.

    This is intended for tasks scheduled from inside Zope.
    """
    abstract = True

    def serialize_args(self, orig_args, orig_kw):
        args = []
        kw = {}
        for arg in orig_args:
            args.append(_serialize_arg(arg))
        for key, value in orig_kw.items():
            kw[key] = _serialize_arg(value)
        return args, kw

    # Override apply_async to register an after-commit hook
    # instead of queueing the task right away and to
    # set object paths instead of objects
    def apply_async(self, args, kwargs):
        args, kw = self.serialize_args(args, kwargs)
        kw['site_path'] = '/'.join(api.portal.get().getPhysicalPath())
        kw['authorized_userid'] = api.user.get_current().getId()

        def hook(success):
            if success:
                super(AfterCommitTask, self).apply_async(args=args, kwargs=kw)
        transaction.get().addAfterCommitHook(hook)


class FunctionRunner(object):

    base_task = AfterCommitTask

    def __init__(self, func, new_func, orig_args, orig_kw):
        self.orig_args = orig_args
        self.orig_kw = orig_kw
        self.func = func
        self.new_func = new_func
        self.userid = None
        self.site = None
        self.app = None

    def deserialize_args(self):
        args = []
        kw = {}
        for arg in self.orig_args:
            args.append(_deserialize_arg(self.app, arg))
        for key, value in self.orig_kw.items():
            kw[key] = _deserialize_arg(self.app, value)

        if len(args) == 0 or not IPloneSiteRoot.providedBy(args[0]):
            args = [self.site] + args
        return args, kw

    def authorize(self):
        pass

    def __call__(self):
        self.app = makerequest(getApp())
        transaction.begin()
        try:
            try:
                self.userid = self.orig_kw.pop('authorized_userid')
                self.site = self.app.unrestrictedTraverse(self.orig_kw.pop('site_path'))  # noqa
                self.authorize()
                args, kw = self.deserialize_args()  # noqa
                # run the task
                result = self.func(*args, **kw)
                # commit transaction
                transaction.commit()
            except ConflictError, e:
                # On ZODB conflicts, retry using celery's mechanism
                transaction.abort()
                raise self.new_func.retry(exc=e)
            except:
                transaction.abort()
                raise
        finally:
            noSecurityManager()
            setSite(None)
            self.app._p_jar.close()

        return result


class AuthorizedFunctionRunner(FunctionRunner):

    def authorize(self):
        notify(BeforeTraverseEvent(self.site, self.site.REQUEST))
        setSite(self.site)

        # set up admin user
        user = api.user.get(self.userid).getUser()
        newSecurityManager(None, user)


class AdminFunctionRunner(AuthorizedFunctionRunner):

    def authorize(self):
        notify(BeforeTraverseEvent(self.site, self.site.REQUEST))
        setSite(self.site)

        # set up admin user
        # XXX need to search for an admin like user otherwise?
        user = api.user.get('admin')
        if user:
            user = user.getUser()
            newSecurityManager(None, user)


class _task(object):
    """Decorator of celery tasks that should be run in a Zope context.

    The decorator function takes a path as a first argument,
    and will take care of traversing to it and passing it
    (presumably a portal) as the first argument to the decorated function.

    Also takes care of initializing the Zope environment,
    running the task within a transaction, and retrying on
    ZODB conflict errors.
    """

    def __call__(self, func, **task_kw):
        def new_func(*args, **kw):
            runner = AuthorizedFunctionRunner(func, new_func, args, kw)
            return runner()
        new_func.__name__ = func.__name__
        return getCelery().task(base=AfterCommitTask, **task_kw)(new_func)

    def as_admin(self, func, **task_kw):
        def new_func(*args, **kw):
            runner = AdminFunctionRunner(func, new_func, args, kw)
            return runner()
        new_func.__name__ = func.__name__
        return getCelery().task(base=AfterCommitTask, **task_kw)(new_func)

task = _task()
