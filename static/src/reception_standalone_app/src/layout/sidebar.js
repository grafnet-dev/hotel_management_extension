/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Link } from "../components/Link";

export class Sidebar extends Component {
  static template = "hotel_management_extension.Sidebar";
  static components = { Link };

  setup() {
    console.log("📦 Sidebar setup");
  }

  get navItems() {
    return [
      { name: "Accueil", to: "/" },
      { name: "À propos", to: "/about" },
      { name: "Sèdjro", to: "/about/sedjro" },
      { name: "Chambres", to: "/rooms" },
       { name: "Reservations", to: "/bookings" },
    ];
  }
}
