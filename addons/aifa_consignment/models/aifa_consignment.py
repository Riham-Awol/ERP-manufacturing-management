# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AifaConsignment(models.Model):
    """Stock placed on a retail partner's shelf but still owned by Aifa (FRS-6.2).

    Modelled as an internal stock transfer into a per-customer location rather
    than as a sale, because that is what it legally is: title has not passed.
    The sale, and therefore the invoice and the VAT, is generated only when a
    shelf count confirms sell-through.
    """

    _name = "aifa.consignment"
    _description = "Consignment Placement"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(required=True, copy=False, readonly=True, default="New", index=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    partner_id = fields.Many2one(
        "res.partner", string="Retail Partner", required=True, tracking=True, index=True,
        domain="[('aifa_is_consignment', '=', True)]",
    )
    channel = fields.Selection(related="partner_id.aifa_channel", store=True, readonly=True)
    product_id = fields.Many2one(
        "product.product", required=True, domain="[('sale_ok', '=', True)]", tracking=True,
    )
    lot_id = fields.Many2one(
        "stock.lot", string="Lot", domain="[('product_id', '=', product_id)]", tracking=True,
    )
    expiration_date = fields.Datetime(related="lot_id.expiration_date", readonly=True)
    quantity_placed = fields.Float(required=True, digits=(12, 2), tracking=True)
    quantity_sold = fields.Float(digits=(12, 2), readonly=True, tracking=True)
    quantity_returned = fields.Float(digits=(12, 2), readonly=True, tracking=True)
    quantity_lost = fields.Float(
        digits=(12, 2), readonly=True, tracking=True,
        help="Counted short without a return: theft, damage or a miscount. Never "
             "silently folded into 'sold'.",
    )
    balance_units = fields.Float(compute="_compute_balance", store=True, digits=(12, 2))
    sell_through_pct = fields.Float(compute="_compute_balance", store=True, digits=(5, 2))
    unit_price = fields.Monetary(required=True, currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, readonly=True,
    )
    value_on_shelf = fields.Monetary(compute="_compute_balance", store=True,
                                     currency_field="currency_id")
    revenue_recognised = fields.Monetary(compute="_compute_balance", store=True,
                                         currency_field="currency_id")

    picking_id = fields.Many2one("stock.picking", string="Placement Transfer", readonly=True)
    count_ids = fields.One2many("aifa.shelf.count.line", "consignment_id", string="Shelf Counts")
    sale_order_ids = fields.Many2many("sale.order", string="Sell-through Orders", readonly=True)
    last_count_date = fields.Date(readonly=True, tracking=True)
    next_count_due = fields.Date(compute="_compute_next_count", store=True)
    state = fields.Selection(
        [("draft", "Draft"), ("placed", "On Shelf"), ("counted", "Partially Sold"),
         ("closed", "Closed"), ("cancel", "Cancelled")],
        default="draft", tracking=True, index=True,
    )
    note = fields.Text()

    _sql_constraints = [
        ("qty_positive", "check(quantity_placed > 0)",
         "The placed quantity must be greater than zero."),
    ]

    @api.depends("quantity_placed", "quantity_sold", "quantity_returned", "quantity_lost",
                 "unit_price")
    def _compute_balance(self):
        for placement in self:
            placement.balance_units = max(
                placement.quantity_placed - placement.quantity_sold
                - placement.quantity_returned - placement.quantity_lost, 0.0
            )
            placement.sell_through_pct = (
                placement.quantity_sold / placement.quantity_placed * 100.0
                if placement.quantity_placed else 0.0
            )
            placement.value_on_shelf = placement.balance_units * placement.unit_price
            placement.revenue_recognised = placement.quantity_sold * placement.unit_price

    @api.depends("last_count_date", "date", "partner_id.aifa_shelf_count_days")
    def _compute_next_count(self):
        for placement in self:
            base = placement.last_count_date or placement.date
            days = placement.partner_id.aifa_shelf_count_days or 14
            placement.next_count_due = (
                fields.Date.add(base, days=days) if base else False
            )

    @api.onchange("product_id", "partner_id")
    def _onchange_price(self):
        if self.product_id:
            pricelist = self.partner_id.property_product_pricelist
            if pricelist:
                self.unit_price = pricelist._get_product_price(
                    self.product_id, 1.0, self.partner_id
                )
            else:
                self.unit_price = self.product_id.list_price

    @api.constrains("lot_id", "product_id")
    def _check_lot_released(self):
        for placement in self:
            if placement.lot_id and placement.lot_id.aifa_quality_state != "released":
                raise ValidationError(
                    _("Lot %(lot)s is %(state)s, not released. Quarantined or pending stock "
                      "must never reach a retail shelf.")
                    % {"lot": placement.lot_id.name,
                       "state": placement.lot_id.aifa_quality_state}
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("aifa.consignment") or "New"
        return super().create(vals_list)

    # ------------------------------------------------------------------ workflow
    def action_place(self):
        """Move the stock into the partner's consignment location."""
        for placement in self:
            if placement.state != "draft":
                raise UserError(_("Only a draft placement can be delivered."))
            placement._create_placement_transfer()
            placement.state = "placed"

    def _create_placement_transfer(self):
        self.ensure_one()
        if self.picking_id:
            return self.picking_id
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        if not warehouse:
            raise UserError(_("No warehouse is configured for %s.") % self.env.company.name)
        dest = self.partner_id._aifa_get_consignment_location()
        picking_type = warehouse.int_type_id
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "partner_id": self.partner_id.id,
            "origin": self.name,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": dest.id,
            "move_ids": [(0, 0, {
                "name": self.name,
                "product_id": self.product_id.id,
                "product_uom_qty": self.quantity_placed,
                "product_uom": self.product_id.uom_id.id,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": dest.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        if self.lot_id:
            for move in picking.move_ids:
                move.move_line_ids.unlink()
                self.env["stock.move.line"].create({
                    "move_id": move.id,
                    "picking_id": picking.id,
                    "product_id": move.product_id.id,
                    "product_uom_id": move.product_uom.id,
                    "lot_id": self.lot_id.id,
                    "quantity": self.quantity_placed,
                    "location_id": move.location_id.id,
                    "location_dest_id": move.location_dest_id.id,
                })
        picking.button_validate()
        self.picking_id = picking
        self.message_post(
            body=_("%(qty)s units placed on the shelf at %(partner)s (transfer %(pick)s). "
                   "Title remains with Aifa Foods until a count confirms the sale.")
            % {"qty": self.quantity_placed, "partner": self.partner_id.name,
               "pick": picking.name}
        )
        return picking

    def action_close(self):
        for placement in self:
            if placement.balance_units > 0:
                raise UserError(
                    _("%(name)s still shows %(qty)s unit(s) on the shelf. Record a final "
                      "count, a return or a loss before closing it.")
                    % {"name": placement.name, "qty": placement.balance_units}
                )
            placement.state = "closed"

    def action_cancel(self):
        for placement in self:
            if placement.quantity_sold:
                raise UserError(
                    _("%s has already been invoiced in part; close it instead of cancelling.")
                    % placement.name
                )
            placement.state = "cancel"

    def action_view_sale_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sell-through Orders"),
            "res_model": "sale.order",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.sale_order_ids.ids)],
        }


class AifaShelfCount(models.Model):
    """A merchandiser's visit: count every placement at one partner, then bill."""

    _name = "aifa.shelf.count"
    _description = "Consignment Shelf Count"
    _inherit = ["mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    partner_id = fields.Many2one(
        "res.partner", required=True, domain="[('aifa_is_consignment', '=', True)]",
        tracking=True,
    )
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    counted_by_id = fields.Many2one("res.users", default=lambda self: self.env.user,
                                    required=True)
    line_ids = fields.One2many("aifa.shelf.count.line", "count_id", string="Counted Lines")
    units_sold = fields.Float(compute="_compute_totals", store=True, digits=(12, 2))
    units_returned = fields.Float(compute="_compute_totals", store=True, digits=(12, 2))
    units_lost = fields.Float(compute="_compute_totals", store=True, digits=(12, 2))
    amount_billable = fields.Monetary(compute="_compute_totals", store=True,
                                      currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, readonly=True,
    )
    sale_order_id = fields.Many2one("sale.order", string="Generated Order", readonly=True,
                                    copy=False)
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"), ("billed", "Billed"),
         ("cancel", "Cancelled")],
        default="draft", tracking=True,
    )
    note = fields.Text()

    @api.depends("partner_id", "date")
    def _compute_name(self):
        for count in self:
            count.name = "COUNT/%s/%s" % (
                count.partner_id.name or "?", count.date or ""
            )

    @api.depends("line_ids.qty_sold", "line_ids.qty_returned", "line_ids.qty_lost",
                 "line_ids.amount")
    def _compute_totals(self):
        for count in self:
            count.units_sold = sum(count.line_ids.mapped("qty_sold"))
            count.units_returned = sum(count.line_ids.mapped("qty_returned"))
            count.units_lost = sum(count.line_ids.mapped("qty_lost"))
            count.amount_billable = sum(count.line_ids.mapped("amount"))

    def action_load_open_placements(self):
        """Pre-fill a line per open placement at this partner."""
        for count in self:
            placements = self.env["aifa.consignment"].search([
                ("partner_id", "=", count.partner_id.id),
                ("state", "in", ("placed", "counted")),
            ])
            if not placements:
                raise UserError(
                    _("There is no open consignment placement at %s.") % count.partner_id.name
                )
            count.line_ids.unlink()
            count.line_ids = [(0, 0, {
                "consignment_id": placement.id,
                "product_id": placement.product_id.id,
                "lot_id": placement.lot_id.id,
                "qty_expected": placement.balance_units,
                "qty_remaining": placement.balance_units,
                "unit_price": placement.unit_price,
            }) for placement in placements]
        return True

    def action_confirm(self):
        for count in self:
            if count.state != "draft":
                raise UserError(_("Only a draft count can be confirmed."))
            if not count.line_ids:
                raise UserError(_("Load the open placements before confirming."))
            for line in count.line_ids:
                line._apply_to_placement()
            count.state = "confirmed"
            if count.units_lost:
                count.message_post(
                    body=_("<b>%(n)s unit(s) counted short</b> without a matching return. "
                           "Investigate before the next visit rather than writing it off.")
                    % {"n": count.units_lost},
                    subtype_xmlid="mail.mt_comment",
                )

    def action_create_sale_order(self):
        """Bill the sell-through: one order line per product actually sold."""
        for count in self:
            if count.state != "confirmed":
                raise UserError(_("Confirm the count before billing it."))
            sellable = count.line_ids.filtered(lambda l: l.qty_sold > 0)
            if not sellable:
                raise UserError(_("Nothing was sold at %s in this count.")
                                % count.partner_id.name)
            order = self.env["sale.order"].create({
                "partner_id": count.partner_id.id,
                "date_order": fields.Datetime.now(),
                "origin": count.name,
                "order_line": [(0, 0, {
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.qty_sold,
                    "price_unit": line.unit_price,
                    "name": _("%(product)s (consignment sell-through, lot %(lot)s)")
                            % {"product": line.product_id.display_name,
                               "lot": line.lot_id.name or "-"},
                }) for line in sellable],
            })
            order.action_confirm()
            count.write({"sale_order_id": order.id, "state": "billed"})
            for line in sellable:
                line.consignment_id.sale_order_ids = [(4, order.id)]
            count.message_post(
                body=_("Sell-through order %(order)s created for %(amt)s.")
                % {"order": order.name, "amt": count.amount_billable}
            )
        return True

    def action_cancel(self):
        self.write({"state": "cancel"})


class AifaShelfCountLine(models.Model):
    _name = "aifa.shelf.count.line"
    _description = "Shelf Count Line"
    _order = "count_id, id"

    count_id = fields.Many2one("aifa.shelf.count", required=True, ondelete="cascade")
    consignment_id = fields.Many2one("aifa.consignment", required=True, ondelete="cascade")
    partner_id = fields.Many2one(related="count_id.partner_id", store=True, readonly=True)
    product_id = fields.Many2one("product.product", required=True)
    lot_id = fields.Many2one("stock.lot")
    qty_expected = fields.Float(string="Expected on Shelf", digits=(12, 2), readonly=True)
    qty_remaining = fields.Float(string="Counted on Shelf", digits=(12, 2), required=True)
    qty_returned = fields.Float(string="Returned (damaged / expired)", digits=(12, 2))
    qty_sold = fields.Float(compute="_compute_sold", store=True, digits=(12, 2))
    qty_lost = fields.Float(compute="_compute_sold", store=True, digits=(12, 2))
    unit_price = fields.Monetary(currency_field="currency_id")
    amount = fields.Monetary(compute="_compute_sold", store=True, currency_field="currency_id")
    currency_id = fields.Many2one(related="count_id.currency_id", readonly=True)
    return_reason = fields.Selection(
        [("expired", "Expired / Near Expiry"), ("damaged", "Damaged Packaging"),
         ("recall", "Recall"), ("slow", "Slow Moving / Delisted")],
        string="Return Reason",
    )
    note = fields.Char()

    @api.depends("qty_expected", "qty_remaining", "qty_returned", "unit_price")
    def _compute_sold(self):
        for line in self:
            consumed = line.qty_expected - line.qty_remaining
            sold = max(consumed - line.qty_returned, 0.0)
            line.qty_sold = sold
            line.qty_lost = 0.0
            line.amount = sold * line.unit_price

    @api.constrains("qty_remaining", "qty_returned", "qty_expected")
    def _check_quantities(self):
        for line in self:
            if line.qty_remaining < 0 or line.qty_returned < 0:
                raise ValidationError(_("Counted quantities cannot be negative."))
            if line.qty_remaining + line.qty_returned > line.qty_expected:
                raise ValidationError(
                    _("%(product)s: counted %(rem)s on shelf plus %(ret)s returned exceeds "
                      "the %(exp)s that were placed. Re-count before confirming; a shelf "
                      "cannot hold more than was delivered to it.")
                    % {"product": line.product_id.display_name, "rem": line.qty_remaining,
                       "ret": line.qty_returned, "exp": line.qty_expected}
                )

    def _apply_to_placement(self):
        self.ensure_one()
        placement = self.consignment_id
        placement.write({
            "quantity_sold": placement.quantity_sold + self.qty_sold,
            "quantity_returned": placement.quantity_returned + self.qty_returned,
            "last_count_date": self.count_id.date,
            "state": "counted" if (placement.balance_units - self.qty_sold
                                   - self.qty_returned) > 0 else "counted",
        })
