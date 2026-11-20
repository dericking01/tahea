# -*- coding: utf-8 -*-
from . import models
from . import wizards
from . import controllers


def _re_post_init_hook(env):
    """Link default real-estate products to every existing company that has
    not been configured yet. Accountants can change them afterwards in
    Real Estate > Configuration > Settings."""
    env['res.company'].search([])._re_set_default_products()
