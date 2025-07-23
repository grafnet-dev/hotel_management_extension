/** @odoo-module **/

import { Component } from "@odoo/owl";

export class Link extends Component {
  static template = "hotel_management_extension.Link";


  navigate(ev) {
    ev.preventDefault();
    const to = this.props.to;
    console.log("🔗 Navigation vers :", to);
    if (window.page) {
      window.page(to);
    } else {
      console.error("❌ page.js non disponible !");
    }
  }
}
