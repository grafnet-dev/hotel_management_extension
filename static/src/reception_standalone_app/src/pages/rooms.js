/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useStore } from "../hooks/useStore";
import { RoomTypeList } from "../components/room_type_list";
import { RoomTypeDetail } from "../components/room_type_details";

export class RoomsPage extends Component {
  static template = "reception_standalone_app.RoomsPage";
  static components = { RoomTypeList, RoomTypeDetail };

setup() {
  console.log("🏠 RoomPage setup");
  const { state } = useStore();

  console.log("💬 [DEBUG] store state", state);
  console.log("💬 [DEBUG] state.rooms", state.rooms);
  console.log("💬 [DEBUG] state.rooms.list", state.rooms.list);

this.state = state;

// on crée un wrapper objet 
// état local propre au composant , Si selectedRoomType est utilisé dans le template, OWL redessinera la vue automatiquemen
this.ui = useState({
  selectedRoomType: null,
});
setTimeout(() => {
  console.log("👁️‍🗨️ Valeur sélectionnée après 1s :", this.ui.selectedRoomType);
}, 1000);


}

onRoomTypeSelect(roomType) {
  console.log("📌 Room type selected:", roomType);
  if (!this.ui) {
    console.error("❗ this.ui is undefined. setup() may not have run yet.");
    return;
  }

  if (roomType && typeof roomType === "object") {
    this.ui.selectedRoomType = roomType;
  } else {
    console.warn("❗ Valeur inattendue pour roomType:", roomType);
  }
}


}
