/** @odoo-module **/

import { Component, useRef, onMounted } from "@odoo/owl";
import { setupRouter } from "./routes";
import { Link } from "./components/Link";

export class Root extends Component {
  static template = "hotel_management_extension.ReceptionStandaloneAppRoot";
  static components = { Link };

  setup() {
    console.log("📦 Root setup");

    const currentComponent = useRef(null);
    const currentProps = useRef({});

    const rerender = () => {
      this.render(); // force le rendu OWL
    };

    setupRouter({
      currentComponent: {
        set: (Component) => {
          currentComponent.value = Component;
          rerender();
        },
      },
      currentProps: {
        set: (props) => {
          currentProps.value = props;
          rerender();
        },
      },
    });

    this.currentComponent = currentComponent;
    this.currentProps = currentProps;
  }
}
