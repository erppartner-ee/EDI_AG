# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    #  Information
    'name': 'eAK: Sync Invoices and vendor bills',
    'version': '17.0.0.1.2',
    'category': 'Customization',
    'summary': "Sync Invoices and vendor bills with eAK API",
    'description': """
        TaskID: 3898908
        - Sync Invoices and vendor bills with eAK API(Max 100)
    """,

    # Author
    'author': 'Odoo PS',
    'license': 'LGPL-3',

    # Dependency
    'depends': [
        'product',
        'account_edi',
        'account_accountant'
    ],
    'data': [
        'data/product_data.xml',
        'data/account_edi_data.xml',
        'data/ir_cron_eak_fetch_bills.xml',
        'data/templates/invoice_export_template.xml',
        'data/templates/invoice_import_template.xml',
        'data/templates/company_status_query.xml',
        'data/templates/invoice_attachment_request.xml',

        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/account_journal_dashboard_views.xml',
        'views/res_config_settings_views.xml',
    ],

    # Other
    'installable': True,
    'auto_install': False,
}
