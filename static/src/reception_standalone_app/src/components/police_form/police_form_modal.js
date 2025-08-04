/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

export class PoliceFormModal extends Component {
  static template = "hotel_management_extension.PoliceFormModal";
  static props = {
    stay: Object,
    onValidate: Function,
    onCancel: Function,
  };

  setup() {
    this.form = useState({
      full_name: this.props.stay.occupant_name,
      nationality: "",
      id_type: "",
      id_number: "",
      gender: "",
    });

    this.submit = () => {
      this.props.onValidate(this.form);
    };
  }
}
