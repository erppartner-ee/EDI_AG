# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from lxml import etree
from odoo import models, fields, _
from .account_edi_eak import EstonianEInvoice


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_edi_eak = fields.Boolean('Send to eAK', readonly=True)

    def _cron_sync_eak_partners(self):
        logger = []
        account_journal = self.env['account.journal']
        companies = self.env['res.company']._get_companies()
        for company in companies:
            eAk_response, error = self._process_to_update_edi_eak_value(company)
            if not error:
                eAk_response.update({'level': 'success'})
            logger.append(account_journal._prepare_logger_values('eAk: Sync Clients Status', company.eak_url, eAk_response))
        self.env['ir.logging'].sudo().create(logger)

    def _process_to_update_edi_eak_value(self, company):
        edi_content, error = self._get_partner_edi_content(company)
        if not error:
            eAk_obj = EstonianEInvoice(company.eak_url)
            eAk_response = eAk_obj.getClientStatus(edi_content)
            if eAk_response.get('fault_string'):
                error = company.name + "\n"+ eAk_response.get('fault_string')
                return eAk_response, error
            error = self._process_to_update_partners(eAk_response.get('row'))
        return eAk_response, error

    def _get_partner_edi_content(self, company):
        domain = [('company_registry', '!=', ''), ('is_company','=', True)]
        error = ""
        partners = self.search(domain)
        regNumbers = partners.mapped('company_registry')
        vals = {
                'authPhrase': company.eak_auth,
                'regNumbers': regNumbers
            }
        edi_content = self.env['ir.qweb']._render('account_edi_eak.company_status_code_import',{'vals': vals})
        return edi_content, error

    def _process_to_update_partners(self, row):
        edi_response = etree.XML(row)
        ns = {
            'erp': 'http://e-arvetekeskus.eu/erp',
            **edi_response.nsmap
        }
        unknown_partners = ''
        partner_tree_list= edi_response.findall(".//SOAP-ENV:Body/erp:CompanyStatusResponse/erp:CompanyActive", ns)
        for partner_tree in partner_tree_list:
            regNumber = partner_tree.attrib['regNumber']
            partner = self.search([('company_registry', '=', regNumber), ('company_registry', '!=', '')], limit=1)
            if partner:
                partner.is_edi_eak = True if partner_tree.text == 'YES' else False
            else:
                unknown_partners += (_(f"Partner regNumber: {regNumber} Not Find"))
        return unknown_partners
