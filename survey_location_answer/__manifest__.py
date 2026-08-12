{
    'name': 'Survey Participation Columns',
    'version': '18.0.2.0.0',
    'category': 'Survey',
    'summary': 'Configurable question-answer columns on survey participations',
    'author': 'Custom',
    'depends': ['survey'],
    'data': [
        'security/ir.model.access.csv',
        'views/survey_participation_column_views.xml',
        'views/survey_user_input_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
