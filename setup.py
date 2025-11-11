from setuptools import setup, find_packages

setup(
    name="snipetrade",
    version="0.1.0",
    description="Modular crypto trade scanner with multi-timeframe analysis",
    author="SnipeTrade",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "ccxt>=4.0.0",
        "requests>=2.31.0",
        "python-telegram-bot>=20.0",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "ta>=0.11.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "snipetrade=snipetrade.cli:main",
        ],
    },
    python_requires=">=3.8",
)
