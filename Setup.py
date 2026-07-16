from setuptools import setup, find_packages

setup(
    name='carteras',
    version='1.0.0',
    description='Análisis de portafolios con filtros fundamentales y evaluación de CEDEARs',
    author='Walter Caamaño',
    packages=find_packages(where='scripts'),
    package_dir={'': 'scripts'},
    include_package_data=True,
    install_requires=[
        'pandas',
        'numpy',
        'yfinance',
        'pdfplumber',
        'camelot-py[cv]',
        'tabula-py',
        'requests',
        'openpyxl',
        'scipy',
        'tk'
    ],
    entry_points={
        'console_scripts': [
            'carteras=Historico:ejecutar_escenarios'
        ]
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)
