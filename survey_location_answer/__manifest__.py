{
    'name': 'Survey Participation Columns & Dropdown Choices',
    'version': '18.0.3.0.0',
    'category': 'Survey',
    'summary': 'Configurable participation columns + searchable dropdown for large choice questions',
    'author': 'Custom',
    'depends': ['survey'],
    'data': [
        'security/ir.model.access.csv',
        'views/survey_participation_column_views.xml',
        'views/survey_user_input_views.xml',
        'views/survey_dropdown_templates.xml',
    ],
    'assets': {
        'survey.survey_assets': [
            'survey_location_answer/static/src/js/survey_dropdown.js',
            'survey_location_answer/static/src/scss/survey_dropdown.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
