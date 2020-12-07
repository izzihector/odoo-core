odoo.define('x2many.next.prev.buttons', function (require) {
    "use strict";

    var core = require('web.core');
    var FormDialog = require('web.view_dialogs');

    var QWeb = core.qweb;
    var _t = core._t;

    var FormViewDialog = FormDialog.FormViewDialog.include({

        init: function (parent, options) {
            var res = this._super(parent, options);
            var readonly = _.isNumber(options.res_id) && options.readonly;
            if (readonly && 'buttons' in this && this.res_model == 'hr.expense') {
                this.buttons.splice(this.buttons.length, 0, {
                    text: _t("Previous"),
                    classes: "btn-primary button-previous-form-dialog",
                    click: function () {
                        this.on_click_form_dialog_previous();
                    },
                }, {
                    text: _t("Next"),
                    classes: "btn-primary button-next-form-dialog",
                    click: function () {
                        this.on_click_form_dialog_next();
                    },
                });
            }
            return res
        },

        on_click_form_dialog_next: function () {
            var options = this.options;
            var parent = this.getParent();
            if (parent && parent.initialState && parent.initialState.data && parent.initialState.data.expense_line_ids) {
                var local_array = parent.initialState.data.expense_line_ids;
                var array_child_ids = local_array.res_ids;
                var index = array_child_ids.indexOf(this.res_id)

                if (index === (array_child_ids.length - 1)) {
                    this.close();
                } else {
                    options.res_id = array_child_ids[index + 1];
                    this.close();
                    new FormDialog.FormViewDialog(parent, options).open();
                }
            }
        },

        on_click_form_dialog_previous: function () {
            var options = this.options;
            var parent = this.getParent();
            if (parent && parent.initialState && parent.initialState.data && parent.initialState.data.expense_line_ids) {
                var local_array = parent.initialState.data.expense_line_ids;
                var array_child_ids = local_array.res_ids;
                var index = array_child_ids.indexOf(this.res_id)
                if (index === 0) {
                    this.close();
                } else {
                    options.res_id = array_child_ids[index - 1];
                    this.close();
                    new FormDialog.FormViewDialog(parent, options).open();
                }
            }
        },
    })
})