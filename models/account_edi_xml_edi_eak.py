# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from lxml import etree
from odoo import models
from odoo.tools.xml_utils import cleanup_xml_node


class AccountEdiXmlEDIeAK(models.AbstractModel):
    _name = 'account.edi.xml.edi_eak'
    _inherit = 'account.edi.common'
    _description = "eAK development"

    def _export_invoice_filename(self, invoice):
        # EXTENDS account_edi_ubl_cii
        return f"{invoice.name.replace('/', '_')}_edi_eak.xml"

    def _export_invoice(self, invoice):
        vals = invoice._prepared_eak_invoice()
        xml_content = self.env['ir.qweb']._render('account_edi_eak.account_invoice_edi_eak_export', {'vals': vals})
        edi_format = invoice.journal_id.edi_format_ids.filtered(lambda edi:edi.code == 'EAKs')
        return etree.tostring(cleanup_xml_node(xml_content, remove_blank_nodes=False), xml_declaration=True, encoding='UTF-8'), edi_format and \
            edi_format[0]._check_move_configuration(invoice) or False
