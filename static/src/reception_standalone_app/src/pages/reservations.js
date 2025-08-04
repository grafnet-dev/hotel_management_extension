/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { ReservationList } from "../components/reservation_list";
import { ReservationDetail } from "../components/reservation_detail";

export class Reservations extends Component {
  static components = { ReservationList, ReservationDetail };
  static template = "hotel_management_extension.Reservations";

  setup() {
    this.state = useState({
      screen: "list",
      selectedBooking: null,
    });

    // ✅ Arrow functions pour préserver le contexte
    this.showDetails = (booking) => {
      console.log("📥 showDetails called with:", booking);
      if (!booking) {
        console.error("❌ No booking provided to showDetails");
        return;
      }
      this.state.selectedBooking = booking;
      this.state.screen = "detail";
    };

    this.backToList = () => {
      this.state.screen = "list";
      this.state.selectedBooking = null;
    };
  }

}
