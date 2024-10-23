# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import binascii
from lxml import etree
from datetime import datetime
from odoo.tools import float_repr
from odoo import fields, models, _
from .account_edi_eak import EstonianEInvoice

DEFAULT_eAK_DATE_FORMAT = '%Y-%m-%d'

class AccountMove(models.Model):
    _inherit = 'account.move'

    eak_edi_response = fields.Text('EAk Response', readonly=True, copy=False)
    eak_edi_bill = fields.Boolean(string='eAK Vendor Bill', readonly=True, copy=False)
    eak_edi_bill_id = fields.Char('eAK Bill Number', readonly=True, copy=False)
    eak_edi_bill_attachment = fields.Boolean(string='Vendor Bill Attachment Processed', readonly=True, copy=False)

    def button_draft(self):
        res = super().button_draft()
        self.filtered("eak_edi_response").write({'eak_edi_response': ''})
        return res

    # -------------------------------------------------------------------------
    # eAK Process Invoice Values
    # -------------------------------------------------------------------------
    def _is_eak_invoice(self):
        return self.move_type == 'out_invoice' and (self.partner_id.is_company \
            and self.partner_id.is_edi_eak or self.partner_id.parent_id.is_edi_eak)

    def format_monetary(self, number, decimal_places=2):
        return float_repr(number, decimal_places)

    def format_date(self, dt=False):
        dt = dt or datetime.now()
        return dt.strftime(DEFAULT_eAK_DATE_FORMAT)

    def _prepared_eak_invoice(self):
        return {
            'authPhrase': self.company_id.eak_auth,
            'Header': self._prepared_header_vals(),
            'InvoiceParties': self._prepared_InvoiceParties_vals(),
            'Invoice': self._prepared_Invoice_vals(),
            'InvoiceInformation': self._prepared_InvoiceInformation_vals(),
            **self._prepared_InvoiceSumGroup_vals(),
            'AttachmentFile': self._prepared_AttachmentFile_vals(),
            'PaymentInfo': self._prepared_PaymentInfo_vals(),
            'Footer': self._prepared_Footer_vals(),
            'invoice_lines': [vals._prepared_eak_invoice_line(self.format_monetary) for vals in \
                self.invoice_line_ids.filtered(lambda x: x.display_type in ['product', False])]
        }

    def _prepared_header_vals(self):
        return {
                'Date': self.format_date(),
                'FileId': datetime.now().strftime("%Y%m%d%H%M%S")+'/'+str(self.id),
                'Version': '1.2'
            }

    def _prepared_Invoice_vals(self):
        return {
            'sellerRegnumber': self.company_id.company_registry,
            'invoiceId': self.id,
            'regNumber': self.partner_id.company_registry,
        }

    def _prepared_InvoiceParties_vals(self):
        return {
            'SellerParty_Name': self.company_id.name,
            'RegNumber': self.company_id.company_registry,
            'BuyerParty_Name': self.partner_id.name, #TODO:Mapping
            'SellerParty_extensionId': 'EE',
            'SellerParty_InformationContent': self.company_id.company_registry,
            'BuyerParty_extensionId': 'EE',
            'BuyerParty_RegNumber': self.partner_id.company_registry,
            'BuyerParty_InformationContent': self.partner_id.company_registry
        }

    def _prepared_InvoiceInformation_vals(self):
        return {
            'Type': 'DEB', #TODO: Static
            'DocumentName': 'ARVE', #TODO: Static
            'InvoiceNumber': self.name,
            'InvoiceDate': self.format_date(self.create_date),
        }

    def _prepared_InvoiceSumGroup_vals(self):
        return {
            'InvoiceSumGroup_TotalSum': self.format_monetary(self.amount_total),
            'InvoiceSumGroup_Rounding': self.format_monetary(self.tax_totals.get('rounding_amount', 0)),
            'InvoiceSumGroup_TotalVATSum': self.format_monetary(self.amount_tax),
            'InvoiceSumGroup_TotalToPay': self.format_monetary(self.amount_total),
            'InvoiceSumGroup_InvoiceSum': self.format_monetary(self.amount_untaxed),
        }

    def _prepared_AttachmentFile_vals(self):
        pdf_content, pdf_name = self.get_invoice_pdf_report_attachment()
        return {
            'FileName': pdf_name,
            'FileBase64': binascii.b2a_base64(pdf_content).decode('ascii')
        }

    def _prepared_PaymentInfo_vals(self):
        return {
            'Currency': 'EUR',
            'PaymentDescription': self.name,
            'Payable': 'YES',
            'PayDueDate': self.format_date(self.invoice_date_due),
            'PaymentTotalSum': self.format_monetary(self.amount_total),
            'PayerName': self.partner_id.name,
            'PaymentId': self.name,
            'PayToAccount': self.company_id.eak_bank_id.acc_number.replace(" ", "") or '',
            'PayToName': self.company_id.name,
        }

    def _prepared_Footer_vals(self):
        return {
            'TotalNumberInvoices': '1',
            'TotalAmount': self.format_monetary(self.amount_untaxed)
        }

    #-------------------------------------------------------------------------
    #  eAK Sync Vendor Bill Attachment
    # -------------------------------------------------------------------------

    def _cron_sync_eak_vendor_attachments(self, batch_size=10):
        cr = self.env.cr
        companies = self.env['res.company']._get_companies()
        domain = [('eak_edi_bill', '=', True), ('eak_edi_bill_attachment', '=', False)]
        account_journal = self.env['account.journal']
        logger = []
        for company in companies:
            eAk_obj = EstonianEInvoice(company.eak_url)
            bills = self.with_company(company).search(domain, limit=batch_size)
            eAk_response, error = bills._send_vendor_bill_attachment_request(eAk_obj)
            if error:
                eAk_response.update({'message': error})
                logger.append(account_journal._prepare_logger_values('eAk: Sync Vendor Bills Attachments', company.eak_url, eAk_response))
            cr.commit()
        self.env['ir.logging'].sudo().create(logger)

    def action_get_eak_invoice_attachment(self):
        self.ensure_one()
        eAk_obj = EstonianEInvoice(self.company_id.eak_url)
        eAk_response, error=self._send_vendor_bill_attachment_request(eAk_obj)
        return {
            'type': 'ir.actions.client',
            'tag': error and 'display_notification' or 'reload',
            'params': {
                'title': _('Vendor Bills Attachment'),
                'type': error and 'danger' or 'info',
                'message': error and eAk_response.get('fault_string') or 'Attachment Created',
                'sticky': False,
            }
        }

    def _send_vendor_bill_attachment_request(self, eAk_obj):
        if not self:
            message="Not have any Attachment for process"
            return {'level': "success", 'row': message}, True
        company = self[0].company_id
        bill_names = self.mapped('eak_edi_bill_id')
        vals = {
                'authPhrase': company.eak_auth,
                'invoiceIds': bill_names
            }
        edi_content = self.env['ir.qweb']._render('account_edi_eak.invoice_attachment_request_eak_import',{'vals': vals})
        eak_response = eAk_obj.getInvoiceAttachment(edi_content)
        if eak_response.get('fault_string', ''):
            error = company.name + "\n"+ eak_response.get('fault_string')
            return eak_response, error
        return self._process_vendor_bill_attachment(eak_response)

    def _process_vendor_bill_attachment(self, eak_res):
        edi_response = etree.XML(eak_res.get('row'))
        ns = {
            'erp': 'http://e-arvetekeskus.eu/erp',
            **edi_response.nsmap
        }
        error = False
        invoice_tree_list= edi_response.findall(".//erp:InvoiceAttachmentResponse/InvoiceAttachment", ns)
        has_bill_attachment_obj = self.env['account.move']
        for invoice_tree in invoice_tree_list:
            invoiceId = invoice_tree.attrib['invoiceId']
            fileName = invoice_tree.attrib['fileName']
            AttachmentContent = invoice_tree.findtext('AttachmentContent')
            res_id = self.filtered(lambda bill:bill.eak_edi_bill_id == invoiceId)
            if res_id:
                has_bill_attachment_obj += res_id
                self._create_attachment(fileName, AttachmentContent, res_id)
        remaining_bills = self - has_bill_attachment_obj
        if remaining_bills:
            error = f"List Of Invoice Not Found\n {remaining_bills.mapped('name')}"
        return eak_res, error

    def _create_attachment(self, subject_name, pdf_content, res_id):
        attachment = self.env['ir.attachment'].create({
            'name': subject_name,
            'type': 'binary',
            'datas': pdf_content.encode('ascii', 'ignore'),
            'res_model': 'account.move',
            'res_id': res_id.id,
            'mimetype': 'application/pdf'
        })
        res_id.eak_edi_bill_attachment=True
        return attachment

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    def _prepared_eak_invoice_line(self, format_monetary):
        vat_id = sum([tax.amount for tax in self.tax_ids])
        line_vals = {
            'ItemEntry_Description': self.name,
            'ItemDetailInfo_ItemUnit': self.product_uom_id.name,
            'ItemDetailInfo_ItemAmount': self.quantity,
            'ItemDetailInfo_ItemPrice': format_monetary(self.price_unit),
            'ItemSum': format_monetary(self.quantity * self.price_unit),
        }
        if self.discount:
            line_discount = (self.price_subtotal / (1 - self.discount / 100.0)) - self.price_subtotal
            line_vals.update(
                {
                    'Addition_AddContent': f'{self.discount} %',
                    'Addition_AddRate': int(self.discount),
                    'Addition_AddSum': format_monetary(line_discount),
                }
            )
        if vat_id:
            vat_sum =  sum([abs(tax.get('balance', 0.0)) for tax in self.compute_all_tax.values()])
            line_vals.update(
                {
                    'VAT_VATRate': int(vat_id),
                    'VAT_VATSum': format_monetary(vat_sum),
                }
            )
        return line_vals
