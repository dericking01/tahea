# -*- coding: utf-8 -*-
################################################################################
#
#    Antler IT Solutions Pvt. Ltd.
#    Copyright (C) 2025-TODAY Antler IT Solutions Pvt. Ltd(<https://www.antlerit.net>).
#    Author: Ridma Gimhani (ridmap@aviorsys.com)
#
#    This program is free software: you can modify
#    it under the terms of the GNU Affero General Public License (AGPL) as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
################################################################################
{
    'name': "Vendor Bill Overpayment Guard",
    'summary': """
        Prevents overpayment of vendor bills by enforcing strict payment validation.""",
    'description': """
        The Over Payment Blocking module ensures financial accuracy by preventing users from making payments that exceed
         the due amount on vendor bills. This helps businesses maintain proper accounting records and avoid accidental 
         overpayments. The module integrates seamlessly with Odoo’s accounting and payment workflows, enhancing 
         financial control and reducing errors.
    """,
    'author': 'Antler IT Solutions Pvt. Ltd.',
    'company': 'Antler IT Solutions Pvt. Ltd.',
    'maintainer': 'Antler IT Solutions Pvt. Ltd.',
    'website': "https://www.antlerit.net",
    'version': '18.0.1.0.0',
    'category': 'Purchases',
    'depends': ['base', 'account'],
    'data': [
    ],
    'css': [
    ],
    'demo': [
    ],
    'images': ['static/description/banner.jpg'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
