# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    eak_url = fields.Char(related='company_id.eak_url', readonly=False)
    eak_auth = fields.Char(related='company_id.eak_auth', readonly=False)
    eak_bill_export_date = fields.Datetime(related='company_id.eak_bill_export_date')
    eak_bank_id = fields.Many2one('res.partner.bank', related='company_id.eak_bank_id', readonly=False)
