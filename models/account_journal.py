# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from lxml import etree
from odoo.exceptions import UserError
from odoo import models, fields, Command, _
from .account_edi_eak import EstonianEInvoice


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _cron_fetch_eak_vendor_bill(self):
        logger = []
        eAk_response= {}
        cron_name = 'eAk: Sync Vendor Bills'
        companies = self.env['res.company']._get_companies()
        for company in companies:
            eAk_obj = EstonianEInvoice(company.eak_url)
            eAk_response = self.process_eak_vendor_bill(eAk_obj, company)
            message = f"\n {company.name} Successfully Run Schedule Action\n {eAk_response.get('fault_string', '')}"
            eAk_response.update({'message': message})
            logger.append(self._prepare_logger_values(cron_name, company.eak_url, eAk_response))
            self.env.cr.commit()
        if not companies:
            eAk_response.update({'message' : "Please add eAk auth token/eAk URL"})
            logger.append(self._prepare_logger_values(cron_name, 'Empty auth/Url', eAk_response))
        self.env['ir.logging'].sudo().create(logger)

    def process_eak_vendor_bill(self, eAk_obj=False, company_id=False):
        if not company_id:
            company_id = self.env.company
            eAk_obj = EstonianEInvoice(company_id.eak_url)
        eak_auth, eAk_response = company_id._get_eak_auth()
        if eak_auth:
            vals = {
                'authPhrase': eak_auth, 
                'from_date': company_id.eak_bill_export_date
            }
            edi_content = self.env['ir.qweb']._render('account_edi_eak.account_invoice_edi_eak_import',{'vals': vals})
            eAk_response = eAk_obj.getVendorBills(edi_content)
            if eAk_response.get('level') != 'error':
                eAk_response, error = self._process_eak_vendor_bill(eAk_response)
                if not error:
                    eAk_response.update({'level': 'success'})
                    company_id.eak_bill_export_date = fields.datetime.now()
                else:
                    eAk_response.update({'error_type': 'info'})
        if self.env.context.get('sticky_notifications'):
            return self._vendor_bill_notifications(eAk_response)
        return eAk_response

    def _process_eak_vendor_bill(self, eAk_response):
        if eAk_response.get('row'):
            row = etree.XML(eAk_response.get('row'))
            invoices = ''
            invoices_vals = ''
            invoices_vals, error = self._prepared_import_eak_invoice(row)
            if not error and not eAk_response.get('fault_string', '') :
                invoices = self.env['account.move'].sudo().create(invoices_vals)
            if error:
                error_message = "\n".join([er for er in error])
                eAk_response.update({'level': 'error', 'fault_string': error_message, 'error_type': 'danger', 'error_raise': True})
        return eAk_response, False if invoices_vals and invoices else True

    def _vendor_bill_notifications(self, eAk_response):
        error_type = eAk_response.get('error_type')
        message = (error_type and " " or "Successfully Process\n") + \
            (eAk_response.get('fault_string', '') if eAk_response.get('level') != 'success' else " ")
        if eAk_response.get('error_raise'):
            raise UserError(message)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Vendor Bills'),
                'type': error_type or 'info',
                'message': message,
                'sticky': False,
            }
        }

    def _prepared_import_eak_invoice(self, response):
        error = []
        inner_errors = []
        tax = self.env['account.tax']
        partner = self.env['res.partner']
        company = self.env['res.company']
        currency = self.env['res.currency']
        product = self.env['product.product']
        partner_bank = self.env['res.partner.bank']
        unmatched_product_id = self.env.ref('account_edi_eak.unmatched_product_account_edi_eak').id

        def _find_id(obj, domain):
            _id = obj.sudo().search(domain, limit=1)
            return _id and _id.id or ''

        def _find_with_company_id(obj, company, domain):
            _id = obj.with_company(company).search(domain, limit=1)
            return _id and _id.id or ''

        def _prepared_InvoiceParties_vals(invoice):
            partner_RegNumber = invoice.findtext('.//InvoiceParties/SellerParty/RegNumber', '')
            partner_domain = [('company_registry', '=', partner_RegNumber)]
            partner_id = _find_with_company_id(partner, company_id, partner_domain)
            if not partner_id:
                error.append(_(f"- Partner Company ID: {partner_RegNumber}"))
            return {
                'partner_id' : partner_id,
            }

        def _prepared_InvoiceInformation_vals(invoice):
            return {
                'ref': invoice.findtext('.//InvoiceInformation/InvoiceNumber', ''),
                'invoice_date': invoice.findtext('.//InvoiceInformation/InvoiceDate', ''),
                'invoice_date_due': invoice.findtext('.//InvoiceInformation/DueDate', '')
            }

        def _prepared_InvoiceSumGroup_vals(invoice):
            return {
            }

        def _prepared_InvoiceItem_vals(lines):
            line_list = []
            for line in lines:
                VATRate = line.findtext('.//VAT/VATRate', '')
                product_default_code = line.findtext('.//ItemReserve/InformationContent', '')
                product_domain = [('default_code', '=', product_default_code), ('default_code', '!=', '')]
                product_id = _find_with_company_id(product, company_id, product_domain)
                tax_domain = [('type_tax_use', '=', 'purchase'), ('amount', '=', float(VATRate)), ('company_id', '=', company_id)]
                tax_id = _find_id(tax, tax_domain)
                if not tax_id:
                    error.append(_(f"- Tax Amount: {VATRate}%"))
                #Find Line Discount Value
                discount = 0
                for add in line.findall('.//Addition'):
                    if add.attrib['addCode'] == 'DSC':
                        discount = float(add.findtext('AddRate', 0))
                line_vals = {
                    'product_id' :product_id or unmatched_product_id,
                    'tax_ids': [tax_id],
                    'quantity': line.findtext('.//ItemAmount', ''),
                    'price_unit': line.findtext('.//ItemPrice', ''),
                    'price_subtotal': line.findtext('.//ItemSum', ''),
                    'price_total': line.findtext('.//ItemTotal', ''),
                    'discount': discount,
                }
                if not product_id:
                    product_name = line.findtext('.//Description', '')
                    line_vals.update({'name': f'{product_default_code} - {product_name}'})
                line_list.append(Command.create(line_vals))
            return line_list

        def _prepared_PaymentInfo_vals(invoice):
            partner_bank_domain= [('acc_number', '=', invoice.findtext('.//PaymentInfo/PayToAccount', '')), ('acc_number', '!=', '')]
            return {
                'partner_bank_id': _find_id(partner_bank, partner_bank_domain),
                'payment_reference' : invoice.findtext('.//PaymentInfo/PaymentDescription', '')
            }

        vendor_bills = []
        for invoice in response.findall('.//Invoice'):
            company_regNumber = invoice.attrib['regNumber']
            company_id = _find_id(company, [('company_registry', '=', company_regNumber), ('company_registry', '!=', '')])
            currency_code = invoice.findtext('.//InvoiceSumGroup/Currency', '')
            currency_id =_find_id(currency, [('name', '=', currency_code)])
            if not company_id:
                error.append(_(f"* Company ID: {company_regNumber} Not Found"))
            if not currency_id:
                error.append(_(f"* Currency Code: {currency_code} Not active"))
            if company_id and currency_id:
                error=[]
                vendor_vals = {
                    'eak_edi_bill': True,
                    'move_type': 'in_invoice',
                    'company_id': company_id,
                    'currency_id': currency_id,
                    'eak_edi_bill_id': invoice.attrib['invoiceId'],
                    **_prepared_InvoiceParties_vals(invoice),
                    **_prepared_InvoiceInformation_vals(invoice),
                    **_prepared_InvoiceSumGroup_vals(invoice),
                    **_prepared_PaymentInfo_vals(invoice),
                    'eak_edi_response': etree.tostring(invoice, encoding='unicode', pretty_print=True),
                    'invoice_line_ids': _prepared_InvoiceItem_vals(invoice.findall('.//InvoiceItem/InvoiceItemGroup/ItemEntry')),
                }
                if error:
                    error.insert(0, (_(f"Company ID: {company_regNumber} Not Founded")))
                    inner_errors += error
                vendor_bills.append(vendor_vals)
        return vendor_bills, inner_errors or error

    def _prepare_logger_values(self, name, eak_url, eAk_response, method="POST"):
        error = eAk_response.get('level') != 'success'
        defaults = {
            'name': name,
            'type': 'server',
            'dbname': self._cr.dbname,
            'level': 'ERROR' if error else 'INFO',
            'path': eak_url,
            'func': method,
            'line': '1',
            'message': eAk_response.get('message') if error else eAk_response.get('row')
        }
        return defaults
