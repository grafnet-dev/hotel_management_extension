/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

export class PoliceFormModal extends Component {
  static template = "hotel_management_extension.PoliceFormModal";
  //Définition des props attendues depuis le parent 
  static props = {
    stay: Object,
    onValidate: Function,
    onCancel: Function,
  };

  setup() {
    console.log("🟣 [PoliceFormModal] Initialisation avec stay  :", this.props.stay);
    //form local state 
    this.form = useState({
      first_name: this.props.stay.occupant_first_name || "",
      last_name: this.props.stay.occupant_last_name || "",
      nationality: "",
      birthplace: "",
      address: "",
      id_type: "",
      id_number: "",
      gender: "",
      id_issue_date: "",
      id_issue_place: "",
      reason: "",
      transport: "",
    });

    this.submit = () => {
      console.log("🟢 [PoliceFormModal.submit] Formulaire en cours de soumission :", this.form);
      this.props.onValidate({ ...this.form });
    };

    this.cancel = () => {
      console.log("🟡 [PoliceFormModal.cancel] Annulation du formulaire");
      this.props.onCancel();
    };
  }
}
