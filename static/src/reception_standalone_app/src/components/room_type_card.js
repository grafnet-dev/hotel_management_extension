/** @odoo-module **/

import { Component } from "@odoo/owl";

export class RoomTypeCard extends Component {
  static template = "reception_standalone_app.RoomTypeCard";
  static props = {
    roomType: Object,
    onClick: Function,
  };

  onClickCard() {
    console.log("🖱️ Clicked:", this.props.roomType.name);
    this.props.onClick?.(this.props.roomType); 
  }
}
