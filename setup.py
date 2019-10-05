import setuptools

VERSION = "0.0.1"

setuptools.setup(
    name="allinpractice",
    packages=setuptools.find_packages(),
    version=VERSION,
    description="All-Inspiration Practice Back-end",
    author="Hugo Wainwright",
    author_email="wainwrighthugo@gmail.com",
    url="https://github.com/frugs/allin-practice-backend",
    keywords=["sc2", "all-inspiration"],
    classifiers=[],
    install_requires=[
        "Flask-OAuthlib",
        "flask",
        "google-cloud-datastore",
        "allinsso",
        "firebase-admin",
    ],
)
