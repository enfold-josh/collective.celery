from setuptools import setup, find_packages
import os

version = '1.1.5.dev0'

setup(name='collective.celery',
      version=version,
      description="Celery for Plone",
      long_description="%s\n%s" % (
          open("README.rst").read(),
          open(os.path.join("docs", "CHANGES.rst")).read()
      ),
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
          "Framework :: Plone",
          "Framework :: Plone :: 5.2",
          "Programming Language :: Python",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
          "Programming Language :: Python :: 3.8",
          "License :: OSI Approved :: GNU General Public License (GPL)",
          "Development Status :: 5 - Production/Stable",
      ],
      keywords='celery async plone',
      author='Nathan Van Gheem',
      author_email='vangheem@gmail.com',
      url='https://github.com/collective/collective.celery',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['collective'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'celery>=4',
          'plone.api'
      ],
      extras_require={
          'test': [
              'plone.app.testing',
              'SQLAlchemy'
          ]
      },
      entry_points="""
      [z3c.autoinclude.plugin]
      target = plone

      [console_scripts]
      pcelery = collective.celery.scripts.ccelery:main
      """,
      )
