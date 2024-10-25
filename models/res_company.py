# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    eak_url = fields.Char('eAk URL', copy=False)
    eak_auth = fields.Char('Auth Phrase', copy=False)
    eak_bill_export_date = fields.Datetime('Last Sync Vendor Bill Date', copy=False, help="Vendor Bill Last Sync eAK date", readonly=True,
                        default=fields.Datetime.now().replace(year=2009, month=7, day=1, hour=0, minute=0, second=0, microsecond=0))
    eak_bank_id = fields.Many2one('res.partner.bank', string='eAK Bank', copy=False)

    def _get_eak_auth(self):
        if not all([self.eak_url, self.eak_auth]):
            return False, {'level': "error", 'error_type': 'danger', 'fault_string': 'Please add eAk auth token/eAk URL'}
        return self.eak_auth, False

    def _get_companies(self):
        company_domain = [('eak_url', '!=', ''), ('eak_auth', '!=', '')]
        companies = self.search(company_domain)
        return companies

    def update_date(self):
        self.eak_bill_export_date = fields.Datetime.now()