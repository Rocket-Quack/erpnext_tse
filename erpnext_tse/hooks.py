app_name = "erpnext_tse"
app_title = "ERPNext TSE"
app_publisher = "RocketQuackIT"
app_description = "TSE Integration für ERPNext"
app_email = "contact@rocketquack.eu"
app_license = "gpl-3.0"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "erpnext_tse",
# 		"logo": "/assets/erpnext_tse/logo.png",
# 		"title": "ERPNext TSE",
# 		"route": "/erpnext_tse",
# 		"has_permission": "erpnext_tse.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/erpnext_tse/css/erpnext_tse.css"
# app_include_js = "/assets/erpnext_tse/js/erpnext_tse.js"

# include js, css files in header of web template
# web_include_css = "/assets/erpnext_tse/css/erpnext_tse.css"
# web_include_js = "/assets/erpnext_tse/js/erpnext_tse.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "erpnext_tse/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
app_include_icons = ["erpnext_tse/icons/icon_tse_app.svg"]

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "erpnext_tse.utils.jinja_methods",
# 	"filters": "erpnext_tse.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "erpnext_tse.install.before_install"
after_install = "erpnext_tse.install.after_install"

# Migration
# ------------
after_migrate = "erpnext_tse.install.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "erpnext_tse.uninstall.before_uninstall"
# after_uninstall = "erpnext_tse.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "erpnext_tse.utils.before_app_install"
# after_app_install = "erpnext_tse.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "erpnext_tse.utils.before_app_uninstall"
# after_app_uninstall = "erpnext_tse.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "erpnext_tse.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "POS Invoice": {
        "before_submit": [
            "erpnext_tse.erpnext_tse.doctype.tse_transaction.tse_transaction.create_tse_transaction_for_pos_invoice",
            "erpnext_tse.erpnext_tse.pos.pos_invoice.pos_invoice_hooks.ensure_tse_transaction_present_and_finished",
        ],
        "on_submit": [
            "erpnext_tse.erpnext_tse.pos.pos_invoice.pos_invoice_hooks.show_tse_signing_success_toast",
        ],
    },
    "TSE Client": {
        "after_insert": "erpnext_tse.erpnext_tse.doctype.tse_client.hooks.set_pos_profile_on_client",
        "on_update": "erpnext_tse.erpnext_tse.doctype.tse_client.hooks.set_pos_profile_on_client",
    },
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"erpnext_tse.tasks.all"
# 	],
# 	"daily": [
# 		"erpnext_tse.tasks.daily"
# 	],
# 	"hourly": [
# 		"erpnext_tse.tasks.hourly"
# 	],
# 	"weekly": [
# 		"erpnext_tse.tasks.weekly"
# 	],
# 	"monthly": [
# 		"erpnext_tse.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "erpnext_tse.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "erpnext_tse.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "erpnext_tse.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["erpnext_tse.utils.before_request"]
# after_request = ["erpnext_tse.utils.after_request"]

# Job Events
# ----------
# before_job = ["erpnext_tse.utils.before_job"]
# after_job = ["erpnext_tse.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"erpnext_tse.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
