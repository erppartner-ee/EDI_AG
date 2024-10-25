# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import requests
from odoo import _
from lxml import etree, html

_logger = logging.getLogger(__name__)
TIMEOUT = 60

class EstonianEInvoice():

    def __init__(self, url):
        self.url = url

    def _synch_with_eAK_api(self, http_method="POST", headers=None, data=None):
        try:
            _logger.info('request url : {}'.format(self.url))
            _logger.info('request data : {}'.format(data))
            _logger.info('request headers : {}'.format(headers))
            response = requests.request(
                    http_method,
                    self.url,
                    headers=headers,
                    data=data,
                    timeout=TIMEOUT)
            if response.status_code != 500:
                response.raise_for_status()
            return self._process_eAK_response(response)
        except requests.HTTPError as e:
            if response.status_code == 401:
                error_message = """An error occurred. This is due to invalid Token"""
            elif response.status_code == 404:
                error_message = """Client Error: Not Found url / Invalid url"""
            elif not error_message:
                error_message = _('Unexpected error ! please report this to your administrator.')
        except Exception as ex:
            error_message = _('Unexpected error ! please report this to your administrator. {}'.format(str(ex)))
        return {'level': "error", 'fault_code': 'server', 'error_type': 'danger', 'fault_string': f'Could not post to eAk. \nError: ({error_message})'}

    def _process_eAK_response(self, response):
        """
            ns0:60 : Illegal authentication phrase
            ns0:80 : Unknown error has occurred. Document already received
            ns0:65 : Compulsory element missing. 'since' attribute missing or illegal value.
        """
        eAK_xml_response = etree.XML(response.text)
        status_code = response.status_code
        row = etree.tostring(eAK_xml_response, encoding='unicode', pretty_print=True)
        _logger.info('response from eAK (HTTP status {}) ::: \n{}'.format(status_code, row))
        vals = {'row': row, 'level': 'info'}
        error_code = int(eAK_xml_response.findtext('.//ErrorCode', True))
        if not error_code and status_code == 200:
            return vals
        fault_code = eAK_xml_response.findtext('.//faultcode', False)
        fault_string = eAK_xml_response.findtext('.//faultstring', False)
        if fault_code and fault_string:
            return {'fault_code': fault_code, 'level': 'error', 'fault_string': f"{fault_code} : {fault_string}", **vals}
        html_errors = html.fromstring(row)
        fault_string = " <br />".join([el.text for el in html_errors.findall(".//span")])
        return {'fault_code': 'html', 'level': 'error', 'fault_string': fault_string, **vals}

    def sendCustomerInvoice(self, data=None):
        headers = {'SOAPAction': '"EInvoice"', 'Content-Type': 'text/xml'}
        return self._synch_with_eAK_api(
            headers=headers,
            data=data,
        )

    def getVendorBills(self, data=None):
        headers = {'SOAPAction': '"BuyInvoiceExportRequest"', 'Content-Type': 'text/xml'}
        return self._synch_with_eAK_api(
            headers=headers,
            data=data,
        )

    def getClientStatus(self, data=None):
        headers = {'SOAPAction': '"CompanyStatusRequest"', 'Content-Type': 'text/xml'}
        return self._synch_with_eAK_api(
            headers=headers,
            data=data,
        )

    def getInvoiceAttachment(self, data=None):
        headers = {'SOAPAction': '"InvoiceAttachmentRequest"', 'Content-Type': 'text/xml'}
        return self._synch_with_eAK_api(
            headers=headers,
            data=data,
        )
