from odoo.tests.common import TransactionCase
from unittest.mock import patch
from odoo.exceptions import ValidationError

class TestSyncEakPartners(TransactionCase):
    
    def setUp(self):
        super(TestSyncEakPartners, self).setUp()

        self.company = self.env['res.company'].create({
            'name': 'Test Company',
            'eak_url': 'https://fake-eak-url.com',
            'eak_auth': 'test_auth'
        })
        
        self.partners = self.env['res.partner'].create([
            {'name': 'Partner 1', 'company_registry': '123456', 'is_company': True},
            {'name': 'Partner 2', 'company_registry': '789101', 'is_company': True},
            {'name': 'Partner 3', 'company_registry': '111213', 'is_company': True},
            {'name': 'Partner 4', 'company_registry': '111213', 'is_company': True},
            
        ])
    
    @patch('odoo.addons.account_edi_eak.models.account_edi_eak.EstonianEInvoice.getClientStatus')
    def test_sync_with_batches(self, mock_get_client_status):
    
        xml_response = '''
        <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Body>
                <erp:CompanyStatusResponse xmlns:erp="http://e-arvetekeskus.eu/erp">
                    <erp:CompanyActive regNumber="123456">YES</erp:CompanyActive>
                </erp:CompanyStatusResponse>
            </SOAP-ENV:Body>
        </SOAP-ENV:Envelope>
        '''
        
        mock_get_client_status.return_value = {
            'row': xml_response
        }

        self.env['res.partner']._cron_sync_eak_partners()
        
        partner_1 = self.env['res.partner'].search([('company_registry', '=', '123456')])
        partner_2 = self.env['res.partner'].search([('company_registry', '=', '789101')])
        
        self.assertEqual(partner_1.is_edi_eak, True)
        self.assertEqual(partner_2.is_edi_eak, False) 

        self.assertEqual(mock_get_client_status.call_count, 1)  # Modify based on the number of batches