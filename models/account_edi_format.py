# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, _
from .account_edi_eak import EstonianEInvoice


class AccountEdiFormat(models.Model):
    _inherit = "account.edi.format"

    def _get_move_applicability(self, invoice):
        self.ensure_one()
        if self.code == 'EAKs' and invoice._is_eak_invoice():
            return {
            'post': self._account_edi_eak,
            'edi_content': self._account_edi_eak_invoice_content,
        }
        return super()._get_move_applicability(invoice)

    def _needs_web_services(self):
        # EXTENDS account.edi.format
        return self.code == 'EAKs' or super(AccountEdiFormat, self)._needs_web_services()

    def _account_edi_eak(self, invoice):
        attachment = ''
        eAk_response = ''
        edi_eak = self.env['account.edi.xml.edi_eak']
        edi_content ,error = edi_eak._export_invoice(invoice)
        if not error:
            eAK =  EstonianEInvoice(invoice.company_id.eak_url)
            eAk_response = eAK.sendCustomerInvoice(data=edi_content)
            attachment = self.env['ir.attachment'].create({
                        'name': edi_eak._export_invoice_filename(invoice),
                        'raw': edi_content,
                        'res_model': 'account.move',
                        'res_id': invoice.id,
                        'mimetype': 'application/xml'
                    })
        else:
            eAk_response = {'level': 'error', 'fault_code': 'validation', 'fault_string':"\n".join([er for er in error])}
        invoice.eak_edi_response = eAk_response.get('row')
        update_vals = self._invoice_update_vals(eAk_response)
        return {
            invoice: {
                'response': eAk_response.get('row', ''),
                'attachment': attachment,
                **update_vals,
            }
        }

    def _invoice_update_vals(self, e_invoice):
        if e_invoice.get('fault_string', ''):
            return {'blocking_level': 'error', 'error': e_invoice.get('fault_string'),}
        return {'success': True}

    def _check_move_configuration(self, invoice):
        errors = super()._check_move_configuration(invoice)
        if self.code != 'EAKs':
            return errors
        if not invoice.partner_id.name:
            errors.append(_("Please set the Customer Name"))
        if not invoice.partner_id.company_registry:
            errors.append(_("Please add Company ID value into Partner"))
        if not invoice.company_id.company_registry:
            errors.append(_("Please add Company ID value into Company"))
        if not invoice.partner_id.contact_address_complete:
            errors.append(_("Please add partner address"))
        if not invoice.partner_bank_id or not invoice.partner_bank_id.acc_number:
            errors.append(_("Please select Recipient Bank"))
        if not all([invoice.company_id.eak_url, invoice.company_id.eak_auth]):
            errors.append(_("Please add eAk auth token/eAk URL"))
        return errors

    def _account_edi_eak_invoice_content(self, invoice):
        builder = self.env['account.edi.xml.edi_eak']
        xml_content, errors = builder._export_invoice(invoice)
        if errors:
            return "".join([
                _("Errors occured while creating the EDI document (format: %s):", builder._description),
                "\n",
                "\n".join(errors)
            ]).encode()
        return xml_content
