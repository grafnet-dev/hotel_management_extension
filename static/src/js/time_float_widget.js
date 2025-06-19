/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class TimeFloatWidget extends Component {
    static template = "hotel_management_extension.time_float_widget";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        const value = this.props.value || 14.0;
        this.hour = Math.floor(value);
        this.minute = Math.round((value - this.hour) * 60);
    }

    onHourChange(ev) {
        this.hour = parseInt(ev.target.value);
        this._updateValue();
    }

    onMinuteChange(ev) {
        this.minute = parseInt(ev.target.value);
        this._updateValue();
    }

    _updateValue() {
        const newValue = this.hour + this.minute / 60;
        this.props.update(newValue);
    }
}

registry.category("fields").add("time_float_picker", {
    component: TimeFloatWidget,
    supportedTypes: ["float"],
});
