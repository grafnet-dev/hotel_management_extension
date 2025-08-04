/** @odoo-module **/

import { Component } from "@odoo/owl";

export class ReservationFormModal extends Component {
  static template = "hotel_management_extension.ReservationFormModal";
  static props = {
    onClose: Function,
    onSave: Function,
  };

  setup() {
    this.newReservation = {
      booking_date: new Date().toISOString().substring(0, 10),
      client: {
        name: "",
        phone: "",
        email: "",
        membership_status: "Standard",
      },
      status: "pending",
      stays: [],
    };
  }

  save() {
    console.log("📤 Envoi du formulaire...");
    this.props.onSave(this.newReservation);
    this.props.onClose();
  }

  close() {
    console.log("❌ Annulation du formulaire");
    this.props.onClose();
  }
}
