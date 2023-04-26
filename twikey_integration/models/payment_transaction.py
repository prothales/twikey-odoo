# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from werkzeug import urls

from odoo import _, models
from odoo.exceptions import ValidationError

from utils import get_twikey_customer

_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'twikey':
            return res

        # _logger.info("Sending transaction request:\n%s", pprint.pformat(payload))

        base_url = self.provider_id.get_base_url()
        twikey_client = self.env["ir.config_parameter"].sudo().get_twikey_client(company=self.env.company)

        twikey_template = self.provider_id.twikey_template_id
        method = self.provider_id.twikey_method

        customer = self.partner_id
        if self.provider_id.allow_tokenization and twikey_template:
            payload = self._twikey_prepare_token_request_payload(customer, base_url, twikey_template.template_id_twikey, method)
            mndt = twikey_client.document.sign(payload)
            # The provider reference is set now to allow fetching the payment status after redirection
            self.provider_reference = mndt.get('MndtId')
            url = mndt.get('url')

            # Store the mandate
            self.env["twikey.mandate.details"].sudo().create({
                "contract_temp_id": twikey_template.id,
                "lang": customer.lang,
                "partner_id": payload.get("customerNumber"),
                "reference": self.provider_reference,
                "url": url,
                "zip": customer.zip if customer.zip else False,
                "address": customer.street if customer.street else False,
                "city": customer.city if customer.city else False,
                "country_id": customer.country_id.id if customer.country_id else False,
            })
        else:
            payload = self._twikey_prepare_payment_request_payload(customer, base_url, twikey_template.template_id_twikey, method)
            paylink = twikey_client.paylink.create(payload)
            # The provider reference is set now to allow fetching the payment status after redirection
            self.provider_reference = paylink.get('id')
            url = paylink.get('url')

        parsed_url = urls.url_parse(url)
        url_params = urls.url_decode(parsed_url.query)
        # Extract the checkout URL from the payment data and add it with its query parameters to the
        # rendering values. Passing the query parameters separately is necessary to prevent them
        # from being stripped off when redirecting the user to the checkout URL, which can happen
        # when only one payment method is enabled and query parameters are provided.
        return {'api_url': url, 'url_params': url_params, 'reference': self.provider_reference}

    def _twikey_prepare_payment_request_payload(self, customer, base_url, template, method):
        """ Create the payload for the payment request based on the transaction values.
        :return: The request payload
        :rtype: dict
        """

        payload = get_twikey_customer(customer)
        payload["redirectUrl"] = urls.url_join(base_url, f'/twikey/status?ref={self.reference}'),
        payload['title'] = self.reference,
        payload['remittance'] = self.reference,
        payload['amount'] = f"{self.amount:.2f}",
        if template:
            payload["ct"] = template
        if method:
            payload["method"] = method

        if self.invoice_ids:
            if len(self.invoice_ids) == 1:
                if self.invoice_ids[0].twikey_invoice_identifier:
                    payload['invoice'] = self.invoice_ids[0].name
                    payload['remittance'] = self.invoice_ids[0].id
                else:
                    _logger.info("Unknown invoice to Twikey, not linking")
            else:
                raise "Unable to combine 2 invoices to the same link for reconciliation reasons"

        return payload

    def _twikey_prepare_token_request_payload(self, customer, base_url, template, method):

        self.tokenize = True
        payload = get_twikey_customer(customer)
        payload["ct"] = template,
        payload["method"] = method,
        payload["redirectUrl"] = urls.url_join(base_url, f'/twikey/status?ref={self.reference}'),
        payload['transactionMessage'] = self.reference,
        payload['transactionAmount'] = f"{self.amount:.2f}",
        if self.invoice_ids:
            if len(self.invoice_ids) == 1:
                if self.invoice_ids[0].twikey_invoice_identifier:
                    payload['invoice'] = self.invoice_ids[0].name
                else:
                    _logger.info("Unknown invoice to Twikey, not linking")
            else:
                raise "Unable to combine 2 invoices to the same link for reconciliation reasons"

        return payload

    def _get_tx_from_notification_data(self, provider_code, notification_data):

        tx = self.search([('reference', '=', notification_data.get('ref')), ('provider_code', '=', 'twikey')])
        if provider_code != 'twikey' or len(tx) == 1:
            return tx
        if not tx:
            raise ValidationError("Twikey: " + _("No transaction found matching reference %s.", notification_data.get('ref')))
        return tx

    def _process_notification_data(self, notification_data):
        """ Override of payment to process the transaction based on webhook data.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider
        :return: None
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'twikey':
            return

        payment_status = notification_data.get('status')
        if not payment_status:
            _logger.debug("No status update for reference %s", self.reference)
            return

        if self.tokenize:
            # Webhook should have come in with the mandate now being signed
            mandate_id = (
                self.env["twikey.mandate.details"].search([("reference", "=", self.provider_reference)])
            )
            if mandate_id.state == 'signed':
                payment_status = 'paid'
                _logger.debug("Tokenized redirect, mandate was %s",mandate_id.state)
                self.env['payment.token'].create({
                    'payment_details': mandate_id.iban,
                    'provider_id': self.provider.id,
                    'partner_id': self.partner.id,
                    'provider_ref': mandate_id.reference,
                    'active': True,
                })
            else:
                payment_status = 'pending'
                _logger.info("Tokenized redirect but mandate was %s",mandate_id.state)

        if payment_status == 'pending':
            self._set_pending()
        elif payment_status == 'authorized':
            self._set_authorized()
        elif payment_status == 'paid':
            self._set_done()
        elif payment_status in ['expired', 'canceled', 'failed']:
            self._set_canceled("Twikey: " + _("Canceled payment with status: %s", payment_status))
        else:
            _logger.info("received data with invalid payment status (%s) for transaction with reference %s",payment_status, self.reference)
            self._set_error("Twikey: " + _("Received data with invalid payment status: %s", payment_status))

    def _get_post_processing_values(self):
        values = super()._get_post_processing_values()
        if self.provider_code != 'twikey':
            return values

        if self.tokenize and values.get('state') in ['draft','pending']:
            # Webhook should have come in with the mandate now being signed
            mandate_id = (self.env["twikey.mandate.details"].search([("reference", "=", self.provider_reference)]))
            if mandate_id.state == 'signed':
                _logger.info("Tokenized poll, mandate was %s",mandate_id.state)
                self.env['payment.token'].create({
                    'payment_details': mandate_id.iban,
                    'provider_id': self.provider_id.id,
                    'partner_id': self.partner_id.id,
                    'provider_ref': mandate_id.reference,
                    'active': True,
                })
                self._set_done()
            else:
                _logger.info("Mandate was in %s for ref %s",mandate_id.state, self.reference)
        return values
