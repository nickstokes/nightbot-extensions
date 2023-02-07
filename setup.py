from setuptools import find_packages, setup

setup(
    name="nightbot_extensions",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'alembic',
        'Flask',
        'Flask_Migrate',
        'flask_sqlalchemy',
        'python-dotenv',
        'requests',
        'schema',
        'SQLAlchemy',
    ],
)