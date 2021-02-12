# -*- coding: utf-8 -*-

from odoo import api, fields, models,_
from odoo.exceptions import UserError
import requests
import json


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    api_key = fields.Char(string="API Key", help="Add Api Key from Twikey")
    module_twikey = fields.Boolean(string="Enable Twikey Integration", helgrp="Use for enable Twikey Integration")
    authorization_token = fields.Char(string="Authorization Token", help="Get from Twikey Authentication Scheduler and use for other APIs.")

    def authenticate(self):
        api_key = self.env['ir.config_parameter'].sudo().get_param('twikey_integration.api_key')
        if api_key:
            try:
                response = requests.post("https://api.beta.twikey.com/creditor", data={'apiToken':api_key})
                param = self.env['ir.config_parameter'].sudo()
                if response.status_code == 200:
                    param.set_param('twikey_integration.authorization_token', json.loads(response.text).get('Authorization'))
            except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.MissingSchema, requests.exceptions.Timeout, requests.exceptions.HTTPError) as e:
                raise exceptions.AccessError(
                    _('The url that this service requested returned an error. Please check your connection or try after sometime.')
                )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update(
            api_key=self.env['ir.config_parameter'].sudo().get_param(
                'twikey_integration.api_key'),
            module_twikey=self.env['ir.config_parameter'].sudo().get_param(
                'twikey_integration.module_twikey'),
            authorization_token=self.env['ir.config_parameter'].sudo().get_param(
                'twikey_integration.authorization_token'),
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        param = self.env['ir.config_parameter'].sudo()

        api_key = self.api_key or False
        module_twikey = self.module_twikey or False
        authorization_token = self.authorization_token or False

        param.set_param('twikey_integration.api_key', api_key)
        param.set_param('twikey_integration.module_twikey', module_twikey)
        param.set_param('twikey_integration.authorization_token', authorization_token)