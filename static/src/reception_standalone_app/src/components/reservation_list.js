/** @odoo-module **/

import { Component } from "@odoo/owl";
import { roomBookingList } from "../data/bookings";


export class ReservationList extends Component {
  static template = "hotel_management_extension.ReservationList";
  static props = {
    onSelect: Function,
  };

  setup() {
    //Arrow function (recommandée)
    this.handleSelect = (booking) => {
      console.log("📤 Reservation selected:", booking);
      if (!this.props.onSelect) {
        console.error("❌ onSelect prop is missing!");
        return;
      }
      this.props.onSelect(booking);
    };
  }

  get bookings() {
    return roomBookingList;
  }
}
