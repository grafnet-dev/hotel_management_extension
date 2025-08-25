/** @odoo-module **/

import { Component } from "@odoo/owl";

export class RoomTypeDetail extends Component {
  static template = "reception_standalone_app.RoomTypeDetail";
  static props = {
    roomType: { type: Object, optional: true }, 
  };

  setup() {
  console.log("🧩 props.roomType reçu :", this.props.roomType);
}

}
