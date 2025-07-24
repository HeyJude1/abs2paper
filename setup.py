from setuptools import setup, find_packages

setup(
    name="abs2paper",
    version="0.1.0",
    description="A RAG-based paper knowledge processing system",
    author="Author",
    author_email="author@example.com",
    packages=find_packages(),
    install_requires=[
        "pymilvus>=2.3.0",
        "pymupdf>=1.22.0",
        "numpy>=1.24.0",
        "requests>=2.28.0",
        "langchain>=0.0.267",
        "pydantic>=2.4.0",
        "python-dotenv>=1.0.0",
        "transformers>=4.30.0",
        "sentencepiece>=0.1.99",
        "torch>=2.0.0",
        "tqdm>=4.65.0",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
) 