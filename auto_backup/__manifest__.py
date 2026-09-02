# -*- coding: utf-8 -*-
{
    'name': "Database Auto-Backup",
    'summary': 'Automated scheduled backups of the database (local and remote SFTP)',
    'description': """
Database Auto-Backup
====================

This module lets an administrator configure automatic backups of one or more
databases. Backups can be stored on the local file system and/or pushed to a
remote server over SFTP.

For every configuration you provide the host, port, backup directory and
database name (sensible defaults are pre-filled). To write to an external
server over SFTP, additionally provide the IP address, username and password.

Scheduling
----------
1. Go to Settings / Technical / Automation / Scheduled Actions.
2. Open the action named 'Backup scheduler'.
3. Activate it and choose how often backups should run.
4. To push backups to a remote location, fill in the SFTP details on the
   backup configuration record.
    """,
    'author': "Derrick Kamara",
    'website': "https://primesoft.co.tz",
    'maintainer': "Derrick Kamara",
    'company': "Primesoft",
    'support': "info@primesoft.co.tz",
    'category': 'Administration/Administration',
    'version': '18.0.1.0.0',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['base'],
    'external_dependencies': {'python': ['paramiko']},

    # always loaded
    'data': [
        'security/user_groups.xml',
        'security/ir.model.access.csv',
        'views/backup_view.xml',
        'data/backup_data.xml',
    ],
    'images': ['static/description/overview.png'],
}
