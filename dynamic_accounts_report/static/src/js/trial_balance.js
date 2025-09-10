odoo.define('dynamic_accounts_report.trial_balance', function(require) {
    'use strict';
    var AbstractAction = require('web.AbstractAction');
    var core = require('web.core');
    var field_utils = require('web.field_utils');
    var rpc = require('web.rpc');
    var session = require('web.session');
    var utils = require('web.utils');

    var QWeb = core.qweb;
    var _t = core._t;
    var framework = require('web.framework');

    var datepicker = require('web.datepicker');
    var time = require('web.time');

    window.click_num = 0;
    var TrialBalance = AbstractAction.extend({
        template: 'TrialTemp',
        events: {
            'click .parent-line': 'journal_line_click',
            'click .child_col1': 'journal_line_click',
            'click #apply_filter': 'apply_filter',
            'click #pdf': 'print_pdf',
            'click #xlsx': 'print_xlsx',
            'click .show-gl': 'show_gl',
            'mousedown div.input-group.date[data-target-input="nearest"]': '_onCalendarIconClick',
        },

        init: function(parent, action) {
            this._super(parent, action);
            this.currency = action.currency;
            this.report_lines = action.report_lines;
            this.wizard_id = action.context.wizard | null;
        },

        start: function() {
            var self = this;
            self.initial_render = true;
            rpc.query({
                model: 'account.trial.balance',
                method: 'create',
                args: [{}]
            }).then(function(t_res) {
                self.wizard_id = t_res;
                self.load_data(self.initial_render);
            })
        },

        load_data: function(initial_render = true) {
            var self = this;
            self.$(".categ").empty();
            try {
                var self = this;
                self._rpc({
                    model: 'account.trial.balance',
                    method: 'view_report',
                    args: [
                        [this.wizard_id]
                    ],
                }).then(function(datas) {
                    _.each(datas['report_lines'], function(rep_lines) {
                        rep_lines.debit = self.format_currency(datas['currency'], rep_lines.debit);
                        rep_lines.credit = self.format_currency(datas['currency'], rep_lines.credit);
                        rep_lines.balance = self.format_currency(datas['currency'], rep_lines.balance);
                    });
                    
                    if (initial_render) {
                        self.$('.filter_view_tb').html(QWeb.render('TrialFilterView', {
                            filter_data: datas['filters'],
                        }));
                        
                        // Initialize select2 for all dropdowns
                        self.$el.find('.journals').select2({
                            placeholder: 'Select Journals...',
                        });
                        self.$el.find('.analytic_accounts').select2({
                            placeholder: 'Select Analytic Accounts...',
                        });
                        self.$el.find('.target_move').select2({
                            placeholder: 'Target Move...',
                        });
                        self.$el.find('.display_account').select2({
                            placeholder: 'Display Accounts...',
                        });
                    }
                    
                    var child = [];
                    self.$('.table_view_tb').html(QWeb.render('TrialTable', {
                        report_lines: datas['report_lines'],
                        filter: datas['filters'],
                        currency: datas['currency'],
                        credit_total: self.format_currency(datas['currency'], datas['debit_total']),
                        debit_total: self.format_currency(datas['currency'], datas['debit_total']),
                    }));

                });

            } catch (el) {
                window.location.href
            }
        },

        show_gl: function(e) {
            var self = this;
            var account_id = $(e.target).attr('data-account-id');
            var options = {
                account_ids: [account_id],
            }

            var action = {
                type: 'ir.actions.client',
                name: 'GL View',
                tag: 'g_l',
                target: 'new',
                domain: [
                    ['account_ids', '=', account_id]
                ],
            }
            return this.do_action(action);
        },

        print_pdf: function(e) {
            e.preventDefault();
            var self = this;
            self._rpc({
                model: 'account.trial.balance',
                method: 'view_report',
                args: [
                    [self.wizard_id]
                ],
            }).then(function(data) {
                var action = {
                    'type': 'ir.actions.report',
                    'report_type': 'qweb-pdf',
                    'report_name': 'dynamic_accounts_report.trial_balance',
                    'report_file': 'dynamic_accounts_report.trial_balance',
                    'data': {
                        'report_data': data
                    },
                    'context': {
                        'active_model': 'account.trial.balance',
                        'landscape': 1,
                        'trial_pdf_report': true
                    },
                    'display_name': 'Trial Balance',
                };
                return self.do_action(action);
            });
        },

        _onCalendarIconClick: function(ev) {
            var $calendarInputGroup = $(ev.currentTarget);
            var calendarOptions = {
                icons: {
                    date: 'fa fa-calendar',
                },
                locale: moment.locale(),
                format: time.getLangDateFormat(),
                widgetParent: 'body',
                allowInputToggle: true,
            };
            $calendarInputGroup.datetimepicker(calendarOptions);
        },

        format_currency: function(currency, amount) {
            if (typeof(amount) != 'number') {
                amount = parseFloat(amount);
            }
            var formatted_value = (parseInt(amount)).toLocaleString(currency[2], {
                minimumFractionDigits: 2
            })
            return formatted_value
        },

        print_xlsx: function() {
            var self = this;
            self._rpc({
                model: 'account.trial.balance',
                method: 'view_report',
                args: [
                    [self.wizard_id]
                ],
            }).then(function(data) {
                var action = {
                    'data': {
                        'model': 'account.trial.balance',
                        'options': JSON.stringify(data['filters']),
                        'output_format': 'xlsx',
                        'report_data': JSON.stringify(data['report_lines']),
                        'report_name': 'Trial Balance',
                        'dfr_data': JSON.stringify(data),
                    },
                };
                self.downloadXlsx(action);
            });
        },

        downloadXlsx: function(action) {
            framework.blockUI();
            session.get_file({
                url: '/dynamic_xlsx_reports',
                data: action.data,
                complete: framework.unblockUI,
                error: (error) => this.call('crash_manager', 'rpc_error', error),
            });
        },

        journal_line_click: function(el) {
            click_num++;
            var self = this;
            var line = $(el.target).parent().data('id');
            return self.do_action({
                type: 'ir.actions.act_window',
                view_type: 'form',
                view_mode: 'form',
                res_model: 'account.move',
                views: [
                    [false, 'form']
                ],
                res_id: line,
                target: 'current',
            });
        },

        apply_filter: function(event) {
            event.preventDefault();
            var self = this;
            self.initial_render = false;
            var filter_data_selected = {};
            
            // Journals filter
            var journal_ids = [];
            var journal_text = [];
            var journal_res = document.getElementById("journal_res");
            var journal_list = $(".journals").select2('data');
            for (var i = 0; i < journal_list.length; i++) {
                if (journal_list[i].element[0].selected === true) {
                    journal_ids.push(parseInt(journal_list[i].id));
                    if (journal_text.includes(journal_list[i].text) === false) {
                        journal_text.push(journal_list[i].text);
                    }
                    journal_res.value = journal_text;
                    journal_res.innerHTML = journal_res.value;
                }
            }
            if (journal_list.length == 0) {
                journal_res.value = "";
                journal_res.innerHTML = "";
            }
            filter_data_selected.journal_ids = journal_ids;

            // Analytic Accounts filter
            var analytic_account_ids = [];
            var analytic_account_text = [];
            var analytic_account_res = document.getElementById("analytic_account_res");
            var analytic_account_list = $(".analytic_accounts").select2('data');
            for (var i = 0; i < analytic_account_list.length; i++) {
                if (analytic_account_list[i].element[0].selected === true) {
                    analytic_account_ids.push(parseInt(analytic_account_list[i].id));
                    if (analytic_account_text.includes(analytic_account_list[i].text) === false) {
                        analytic_account_text.push(analytic_account_list[i].text);
                    }
                    analytic_account_res.value = analytic_account_text;
                    analytic_account_res.innerHTML = analytic_account_res.value;
                }
            }
            if (analytic_account_list.length == 0) {
                analytic_account_res.value = "";
                analytic_account_res.innerHTML = "";
            }
            filter_data_selected.analytic_account_ids = analytic_account_ids;

            // Date filters
            if (this.$el.find('.datetimepicker-input[name="date_from"]').val()) {
                filter_data_selected.date_from = moment(this.$el.find('.datetimepicker-input[name="date_from"]').val(), time.getLangDateFormat()).locale('en').format('YYYY-MM-DD');
            }
            if (this.$el.find('.datetimepicker-input[name="date_to"]').val()) {
                filter_data_selected.date_to = moment(this.$el.find('.datetimepicker-input[name="date_to"]').val(), time.getLangDateFormat()).locale('en').format('YYYY-MM-DD');
            }

            // Target Move filter
            if ($(".target_move").length) {
                var post_res = document.getElementById("post_res")
                filter_data_selected.target_move = $(".target_move")[1].value
                post_res.value = $(".target_move")[1].value
                post_res.innerHTML = post_res.value;
                if ($(".target_move")[1].value == "") {
                    post_res.innerHTML = "posted";
                }
            }

            // Display Accounts filter
            if ($(".display_account").length) {
                var display_account_res = document.getElementById("display_account_res");
                var display_account_select = $("#display_accounts");
                var selectedOption = display_account_select.find("option:selected").text();
                filter_data_selected.display_account = display_account_select.val();
                display_account_res.innerHTML = selectedOption;
            }

            rpc.query({
                model: 'account.trial.balance',
                method: 'write',
                args: [
                    self.wizard_id, filter_data_selected
                ],
            }).then(function(res) {
                self.initial_render = false;
                self.load_data(self.initial_render);
            });
        },
    });
    
    core.action_registry.add("t_b", TrialBalance);
    return TrialBalance;
});