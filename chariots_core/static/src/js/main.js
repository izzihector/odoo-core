odoo.define('chariots_core.Main', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var ListController = require('web.ListController');
    var session = require('web.session');
    var ajax = require('web.ajax');
    var core = require('web.core');
    var rpc = require("web.rpc");
    var Dialog = require("web.Dialog");
    var qweb = core.qweb;

    FormController.include({
        _onButtonClicked: function (event) {
            var self = this;
            if (event.data.attrs.id === "download-excel-invoice") {
                var data = self.renderer.state.data;
                var date_from = data['initial_date'].format('YYYY-MM-DD');
                var date_to = data['end_date'].format('YYYY-MM-DD');
                var type = data['type']
                var suppliers = []
                var customers = []
                var customer_ids = data['customer_ids']['data']
                var supplier_ids = data['supplier_ids']['data']
                if(customer_ids != undefined){
                    for (var record in customer_ids) {
                        var customer_id = customer_ids[record]['data']['id'];
                        customers.push(customer_id);
                    }
                }
                if(supplier_ids != undefined){
                    for (var record in supplier_ids) {
                        var supplier_id = supplier_ids[record]['data']['id'];
                        suppliers.push(supplier_id);
                    }
                } 
                session.get_file({
                    url: '/chariots/download_excel_invoice',
                    data: {
                        date_from: date_from,
                        date_to: date_to,
                        supplier_ids: JSON.stringify(suppliers),
                        customer_ids: JSON.stringify(customers),
                        type: type
                    }
                });
                return false;
            }
            this._super(event);
        },
    });
});
