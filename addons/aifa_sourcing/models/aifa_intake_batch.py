# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from .aifa_grade_price import GRADES


class AifaIntakeBatch(models.Model):
    """One farmer + one crop + one weighing = one traceable raw lot (FRS-1.5).

    This is the root node of the whole genealogy tree.  Every gram of finished
    product must be reachable from exactly one of these records, which is why
    the lot number is generated here and never entered by hand.

    Lot number layout::

        LOT-RAW-<CROP>-<REGION>-<YYYYMM>-<00001>
        LOT-RAW-PINE-GMA-202609-00042

    The sequence segment restarts nowhere: it is the global intake sequence, so
    the number is unique even if two regions ship on the same day.
    """

    _name = "aifa.intake.batch"
    _description = "Raw Fruit Intake Batch"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "intake_date desc, id desc"

    name = fields.Char(required=True, copy=False, readonly=True, default="New", index=True)
    lot_number = fields.Char(
        copy=False, readonly=True, index=True, tracking=True,
        help="Human-readable traceability lot number printed on the crate label.",
    )
    field_purchase_id = fields.Many2one(
        "aifa.field.purchase", string="Field Purchase", ondelete="set null", readonly=True,
    )
    farmer_id = fields.Many2one("aifa.farmer", required=True, tracking=True, index=True)
    plot_id = fields.Many2one("aifa.farmer.plot", domain="[('farmer_id', '=', farmer_id)]")
    cooperative_id = fields.Many2one(
        related="farmer_id.cooperative_id", store=True, readonly=True,
    )
    crop_id = fields.Many2one("aifa.crop", required=True, tracking=True, index=True)
    variety_id = fields.Many2one("aifa.crop.variety", domain="[('crop_id', '=', crop_id)]")
    centre_id = fields.Many2one("aifa.collection.centre", required=True)
    region_id = fields.Many2one(related="centre_id.region_id", store=True, readonly=True, index=True)
    intake_date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    harvest_date = fields.Date(help="Date the fruit was actually picked, if different.")

    # ----- weighing -----
    gross_weight_kg = fields.Float(required=True, digits=(12, 3), tracking=True)
    crate_count = fields.Integer(string="Crates")
    crate_tare_kg = fields.Float(string="Crate Tare (kg)", default=1.8, digits=(8, 3))
    net_weight_kg = fields.Float(compute="_compute_weights", store=True, digits=(12, 3),
                                 tracking=True)
    rejected_weight_kg = fields.Float(
        digits=(12, 3), tracking=True,
        help="Fruit refused at the gate: rotten, over-ripe, foreign matter, pest damage.",
    )
    accepted_weight_kg = fields.Float(compute="_compute_weights", store=True, digits=(12, 3),
                                      tracking=True)
    rejection_rate = fields.Float(compute="_compute_weights", store=True, digits=(5, 2),
                                  string="Rejection Rate (%)")
    scale_serial = fields.Char(string="Scale ID")

    # ----- quality at the gate (FRS-4.1) -----
    field_grade = fields.Selection(GRADES, string="Field Grade", default="a", required=True)
    gate_grade = fields.Selection(
        GRADES, string="Gate Grade", tracking=True,
        help="Grade confirmed by the receiving inspector at the plant; overrides the field grade "
             "for payout purposes when it differs.",
    )
    brix = fields.Float(string="Brix (degrees)", digits=(5, 2))
    decay_index = fields.Float(
        string="Visual Decay (%)", digits=(5, 2),
        help="Share of the consignment showing decay, bruising or mould.",
    )
    pulp_temp_c = fields.Float(string="Pulp Temperature (C)", digits=(5, 2))
    foreign_matter = fields.Boolean(string="Foreign Matter Found")
    qa_note = fields.Text(string="Inspection Note")
    qa_user_id = fields.Many2one("res.users", string="Receiving Inspector", readonly=True)
    qa_datetime = fields.Datetime(readonly=True)

    # ----- commercials -----
    price_per_kg = fields.Monetary(currency_field="currency_id", tracking=True)
    amount_total = fields.Monetary(compute="_compute_weights", store=True,
                                   currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, readonly=True,
    )
    payout_id = fields.Many2one("aifa.farmer.payout", readonly=True, copy=False, index=True)

    # ----- stock integration -----
    product_id = fields.Many2one(
        "product.product", compute="_compute_product", store=True, readonly=True,
    )
    lot_id = fields.Many2one("stock.lot", string="Stock Lot", readonly=True, copy=False)
    picking_id = fields.Many2one("stock.picking", string="Receipt", readonly=True, copy=False)
    location_dest_id = fields.Many2one(
        "stock.location", string="Destination",
        domain="[('usage', '=', 'internal')]",
        help="Cold room or raw holding bay the consignment is put away to.",
    )

    state = fields.Selection(
        [("draft", "Draft"),
         ("weighed", "Weighed at Depot"),
         ("in_transit", "In Transit"),
         ("received", "Received at Plant"),
         ("accepted", "QA Accepted"),
         ("rejected", "QA Rejected"),
         ("done", "Stocked"),
         ("cancel", "Cancelled")],
        default="draft", tracking=True, copy=False, index=True,
    )

    # ----- offline sync -----
    client_ref = fields.Char(copy=False, index=True, readonly=True)
    gps_lat = fields.Float(digits=(10, 6))
    gps_lng = fields.Float(digits=(10, 6))

    _sql_constraints = [
        ("lot_number_uniq", "unique(lot_number)", "The intake lot number must be unique."),
        ("client_ref_uniq", "unique(client_ref)",
         "This intake batch was already synchronised from the mobile device."),
        ("gross_positive", "check(gross_weight_kg >= 0)", "Gross weight cannot be negative."),
    ]

    # ------------------------------------------------------------------ compute
    @api.depends("gross_weight_kg", "crate_count", "crate_tare_kg",
                 "rejected_weight_kg", "price_per_kg")
    def _compute_weights(self):
        for batch in self:
            tare = batch.crate_count * batch.crate_tare_kg
            net = max(batch.gross_weight_kg - tare, 0.0)
            batch.net_weight_kg = net
            batch.accepted_weight_kg = max(net - batch.rejected_weight_kg, 0.0)
            batch.rejection_rate = (batch.rejected_weight_kg / net * 100.0) if net else 0.0
            batch.amount_total = batch.accepted_weight_kg * batch.price_per_kg

    @api.depends("crop_id")
    def _compute_product(self):
        for batch in self:
            batch.product_id = batch.crop_id.raw_product_id

    @api.constrains("rejected_weight_kg", "gross_weight_kg", "crate_count", "crate_tare_kg")
    def _check_rejected(self):
        for batch in self:
            if batch.rejected_weight_kg > batch.net_weight_kg:
                raise ValidationError(
                    _("Rejected weight (%(rej)s kg) cannot exceed the net weight (%(net)s kg) "
                      "on %(name)s.")
                    % {"rej": batch.rejected_weight_kg, "net": batch.net_weight_kg,
                       "name": batch.name}
                )

    @api.onchange("crop_id", "field_grade", "centre_id")
    def _onchange_price(self):
        if self.crop_id and self.field_grade:
            price = self.env["aifa.grade.price"].resolve(
                self.crop_id, self.field_grade,
                region=self.centre_id.region_id, date=self.intake_date,
            )
            if price:
                self.price_per_kg = price.price_per_kg

    # ------------------------------------------------------------------ CRUD
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("aifa.intake.batch") or "New"
        return super().create(vals_list)

    def _build_lot_number(self):
        """LOT-RAW-<CROP>-<REGION>-<YYYYMM>-<serial from self.name>."""
        self.ensure_one()
        serial = (self.name or "").rsplit("/", 1)[-1]
        return "LOT-RAW-%s-%s-%s-%s" % (
            self.crop_id.code,
            self.region_id.code or "XXX",
            fields.Date.to_date(self.intake_date).strftime("%Y%m"),
            serial,
        )

    # ------------------------------------------------------------------ workflow
    def action_weigh(self):
        for batch in self:
            if batch.state != "draft":
                raise UserError(_("Only a draft intake can be weighed."))
            if batch.gross_weight_kg <= 0:
                raise UserError(_("Record a gross weight before confirming the weighing."))
            batch.state = "weighed"

    def action_receive(self):
        """Gate reception at the plant: assign the traceability lot number."""
        for batch in self:
            if batch.state not in ("weighed", "in_transit"):
                raise UserError(
                    _("%s must be weighed at the depot before it can be received.") % batch.name
                )
            if not batch.crop_id.raw_product_id:
                raise UserError(
                    _("Crop %s has no raw fruit product configured; set it in "
                      "Configuration > Master Data > Crops.") % batch.crop_id.display_name
                )
            if not batch.lot_number:
                batch.lot_number = batch._build_lot_number()
            batch.state = "received"
            batch.message_post(body=_("Received at plant. Traceability lot <b>%s</b> assigned.")
                               % batch.lot_number)

    def action_qa_accept(self):
        """Receiving inspector signs off (FRS-4.1) and stock is created."""
        for batch in self:
            if batch.state != "received":
                raise UserError(_("%s must be received before QA sign-off.") % batch.name)
            batch._check_gate_quality()
            batch.write({
                "state": "accepted",
                "qa_user_id": self.env.user.id,
                "qa_datetime": fields.Datetime.now(),
                "gate_grade": batch.gate_grade or batch.field_grade,
            })
            batch._sync_price_to_gate_grade()
            batch._create_stock_receipt()
        return True

    def action_qa_reject(self):
        for batch in self:
            if batch.state not in ("received", "accepted"):
                raise UserError(_("Only a received batch can be rejected."))
            if not batch.qa_note:
                raise UserError(
                    _("Record an inspection note explaining why %s is rejected.") % batch.name
                )
            batch.write({
                "state": "rejected",
                "qa_user_id": self.env.user.id,
                "qa_datetime": fields.Datetime.now(),
            })
            batch.message_post(body=_("Consignment rejected at the gate: %s") % batch.qa_note)

    def action_cancel(self):
        for batch in self:
            if batch.picking_id and batch.picking_id.state == "done":
                raise UserError(
                    _("%s is already in stock; reverse the receipt before cancelling.") % batch.name
                )
            batch.state = "cancel"

    def action_draft(self):
        self.filtered(lambda b: b.state in ("cancel", "rejected")).write({"state": "draft"})

    def _check_gate_quality(self):
        """Advisory gate checks. Hard blocks live in aifa_quality; here we warn."""
        self.ensure_one()
        crop = self.crop_id
        problems = []
        if crop.min_brix and self.brix and self.brix < crop.min_brix:
            problems.append(
                _("Brix %(got)s is below the %(min)s minimum for %(crop)s.")
                % {"got": self.brix, "min": crop.min_brix, "crop": crop.display_name}
            )
        if self.foreign_matter:
            problems.append(_("Foreign matter was flagged at reception."))
        if self.decay_index and self.decay_index > 10.0:
            problems.append(_("Visual decay of %s%% exceeds the 10%% action limit.")
                            % self.decay_index)
        if problems:
            self.message_post(
                body=_("<b>Gate quality warnings</b><ul>%s</ul>")
                % "".join("<li>%s</li>" % p for p in problems),
                subtype_xmlid="mail.mt_comment",
            )

    def _sync_price_to_gate_grade(self):
        """If the inspector downgrades the consignment, re-price it."""
        self.ensure_one()
        if self.gate_grade and self.gate_grade != self.field_grade:
            new_price = self.env["aifa.grade.price"].resolve(
                self.crop_id, self.gate_grade, region=self.region_id, date=self.intake_date
            )
            if new_price:
                old = self.price_per_kg
                self.price_per_kg = new_price.price_per_kg
                self.message_post(
                    body=_("Re-graded %(f)s -> %(g)s at the gate; price adjusted "
                           "%(old)s -> %(new)s per kg.")
                    % {"f": (self.field_grade or "").upper(), "g": self.gate_grade.upper(),
                       "old": old, "new": self.price_per_kg}
                )

    # ------------------------------------------------------------------ stock
    def _get_receipt_picking_type(self):
        self.ensure_one()
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        if not warehouse:
            raise UserError(_("No warehouse is configured for %s.") % self.env.company.name)
        return warehouse.in_type_id

    def _prepare_lot_values(self):
        self.ensure_one()
        return {
            "name": self.lot_number,
            "product_id": self.product_id.id,
            "company_id": self.env.company.id,
            "ref": self.name,
        }

    def _create_stock_receipt(self):
        """Create and validate the incoming move that puts the fruit in stock."""
        self.ensure_one()
        if self.picking_id:
            return self.picking_id
        if self.accepted_weight_kg <= 0:
            return False
        picking_type = self._get_receipt_picking_type()
        lot = self.env["stock.lot"].create(self._prepare_lot_values())
        dest = self.location_dest_id or picking_type.default_location_dest_id
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "partner_id": self.farmer_id.partner_id.id,
            "origin": "%s / %s" % (self.name, self.lot_number),
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": dest.id,
            "move_ids": [(0, 0, {
                "name": self.lot_number,
                "product_id": self.product_id.id,
                "product_uom_qty": self.accepted_weight_kg,
                "product_uom": self.product_id.uom_id.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": dest.id,
            })],
        })
        picking.action_confirm()
        for move in picking.move_ids:
            move.move_line_ids.unlink()
            self.env["stock.move.line"].create({
                "move_id": move.id,
                "picking_id": picking.id,
                "product_id": move.product_id.id,
                "product_uom_id": move.product_uom.id,
                "lot_id": lot.id,
                "quantity": self.accepted_weight_kg,
                "location_id": move.location_id.id,
                "location_dest_id": move.location_dest_id.id,
            })
        picking.button_validate()
        self.write({"lot_id": lot.id, "picking_id": picking.id, "state": "done"})
        self.message_post(
            body=_("%(qty)s kg stocked under lot <b>%(lot)s</b> (receipt %(pick)s).")
            % {"qty": round(self.accepted_weight_kg, 2), "lot": lot.name, "pick": picking.name}
        )
        return picking

    # ------------------------------------------------------------------ actions
    def action_open_lot(self):
        self.ensure_one()
        if not self.lot_id:
            raise UserError(_("No stock lot has been created for %s yet.") % self.name)
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.lot",
            "res_id": self.lot_id.id,
            "view_mode": "form",
        }

    def action_print_crate_label(self):
        return self.env.ref("aifa_sourcing.action_report_intake_label").report_action(self)

    @api.depends("name", "lot_number")
    def _compute_display_name(self):
        for batch in self:
            batch.display_name = batch.lot_number or batch.name or ""

    # ------------------------------------------------------------------ API
    def _api_payload(self):
        """Compact JSON representation returned to the offline mobile client."""
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "lot_number": self.lot_number,
            "state": self.state,
            "farmer_ref": self.farmer_id.ref,
            "farmer_name": self.farmer_id.name,
            "crop_code": self.crop_id.code,
            "centre_code": self.centre_id.code,
            "region_code": self.region_id.code,
            "intake_date": str(self.intake_date) if self.intake_date else None,
            "gross_weight_kg": self.gross_weight_kg,
            "net_weight_kg": self.net_weight_kg,
            "accepted_weight_kg": self.accepted_weight_kg,
            "grade": self.gate_grade or self.field_grade,
            "price_per_kg": self.price_per_kg,
            "amount_total": self.amount_total,
            "currency": self.currency_id.name,
        }
