Releasing a New Version
=======================
0. Run `python setup.py test`

1. Change the MAJOR, MINOR, MICRO version numbers in `setup.py` as appropriate

2. Set `ISRELEASE=True` in `setup.py`

3. Run `python setup.py build sdist` to generate `schemaperfect/version.py`

4. Commit the changes and tag the release; e.g.
```
   git add . -u
   git commit -m "MAINT: release version 0.1"
   git tag -a v0.1 -m "version 0.1 release"
```
   and push tag to origin

5. Upload to PyPI (requires maintainer permissions) using `twine upload dist/schemaperfect-0.1.0.tar.gz`

6. Update to the next minor version in setup.py, and set `ISRELEASE=False`

7. Commit to master and push to origin
