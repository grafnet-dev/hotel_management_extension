/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Header } from "./header";
import { Sidebar } from "./sidebar";


export class Layout extends Component {
  static template = "hotel_management_extension.Layout";
  static components = { Header, Sidebar };

  setup() {
    console.log("📦 Layout setup");
    console.log("📊 props reçues :", this.props);
  }
}
