# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Payment Provider: Twikey",
    "version": "15.0-subver-dev",
    "category": "Accounting/Payment Providers",
    "summary": "focus on recurring payments",
    'author': "Twikey N.V.",
    'website': "https://www.twikey.com/partner/odoo.html",
    "depends": [
        "payment",
        "account",
        "contacts",
        "sale",
    ],
    "data": [
        "data/schedulers.xml",
        "data/mail_template.xml",
        "data/product_data.xml",
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/res_partner_view.xml",
        "views/contract_template.xml",

        'views/payment_twikey_templates.xml',
        'views/payment_views.xml',
        'data/payment_acquirer_data.xml',

        "wizard/wizard_cancel_reason.xml",
        "wizard/twikey_contract_template_wizard.xml",
        "views/mandate_details.xml",
        "views/account_move.xml",
        "report/report_account_invoice.xml",
    ],
    'application': False,
    'uninstall_hook': 'uninstall_hook',
    "installable": True,
    "images": ["static/description/icon.png"],
    "auto_install": False,
    'license': 'LGPL-3',
}
