/** @odoo-module **/

import { Component } from "@odoo/owl";
import { RoomTypeCard } from "../components/room_type_card";

export class RoomTypeList extends Component {
  static template = "reception_standalone_app.RoomTypeList";
  static components = { RoomTypeCard };
  static props = {
    roomTypes: Array,
    onSelectRoomType: Function,
  };
}
