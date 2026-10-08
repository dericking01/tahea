# -*- coding: utf-8 -*-
from . import models


def post_init_hook(env):
    """Fill the employee responsible on existing transfers from their user."""
    env.cr.execute("""
        UPDATE stock_picking sp
           SET responsible_employee_id = e.id
          FROM hr_employee e
         WHERE e.user_id = sp.user_id
           AND e.company_id = sp.company_id
           AND sp.responsible_employee_id IS NULL
    """)
