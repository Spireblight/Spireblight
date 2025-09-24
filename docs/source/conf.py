# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import sys
from pathlib import Path

sys.path.insert(0, str(Path('..', '..').resolve()))

from src import config

config.load() # likely no user config to speak of, but load it anyway

add_module_names = False
python_use_unqualified_type_names = True

project = 'Spireblight'
author = 'Anilyka Barry, Olivia Thiderman, Spireblight Development Team'
copyright = '2022-2025, ' + author
release = config.__version__

html_theme_options = {
    "icon_links": [
        {
            "name": "GitHub",
            "url": config.__github__,
            "icon": "fab fa-github-square",
            "type": "fontawesome",
        }
    ]
}

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.viewcode']

autodoc_default_options = {"member-order": "bysource"}

templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'pydata_sphinx_theme'
html_static_path = ['_static']
html_favicon = "favicon.ico"
