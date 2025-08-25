/** @odoo-module **/

import { Component } from "@odoo/owl";

export class Header extends Component {
  static template = "hotel_management_extension.Header";

  setup() {
    console.log("📦 Header setup");
  }

  onLogout() {
    console.log("🔓 Déconnexion demandée");
    alert("Déconnexion (pas encore implémentée)");
  }
}
