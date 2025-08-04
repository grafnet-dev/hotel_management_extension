/** @odoo-module **/

import { Component, useRef, onMounted } from "@odoo/owl";
import { setupRouter } from "./routes";
import { Link } from "./components/Link";
import { Layout } from "./layout/layout";
import { useEnv } from "@odoo/owl";
import { useStore } from "./hooks/useStore";

export class Root extends Component {
  static template = "hotel_management_extension.ReceptionStandaloneAppRoot";
  static components = { Layout, Link };

  setup() {
    console.log("📦 Root setup");
    const env = useEnv();
    console.log("ENV par défaut injecté par mountComponent:", env);
    //const store = useService("hm_reception_store");

    const { state, actions } = useStore();
    this.state = state;
    this.actions = actions;
    console.log("📊 État du store:", this.state);
    console.log("🔧 Actions disponibles:", Object.keys(this.actions));

    onMounted(() => {
      console.log("🎭 Root mounted:");
      console.log("  - currentComponent:", this.currentComponent.value);
      console.log("  - currentProps:", this.currentProps.value);
      console.log("📊 État du storeaprèsnmontage:", this.state);
      console.log(
        "🔧 Actions disponibles après montage:",
        Object.keys(this.actions)
      );
      console.log("acceder au rooms, ", this.state);
    });

    // Initialisation avec des valeurs par défaut
    const currentComponent = useRef(null);
    const currentProps = useRef({});

    const rerender = () => {
      console.log("🔄 Rerender appelé");
      console.log("📊 currentComponent.value:", currentComponent.value);
      console.log("📊 currentProps.value:", currentProps.value);
      this.render(); // force le rendu OWL
    };

    setupRouter({
      currentComponent: {
        set: (Component) => {
          console.log("🎯 Nouveau composant défini:", Component);
          currentComponent.value = Component;
          rerender();
        },
      },
      currentProps: {
        set: (props) => {
          console.log("🎯 Nouvelles props définies:", props);
          currentProps.value = props;
          rerender();
        },
      },
    });

    this.currentComponent = currentComponent;
    this.currentProps = currentProps;

    // Log initial des valeurs
    console.log("📊 Valeurs initiales:");
    console.log("  - currentComponent.value:", currentComponent.value);
    console.log("  - currentProps.value:", currentProps.value);
  }

  get layoutProps() {
    return {
      currentComponent: this.currentComponent.value,
      currentProps: this.currentProps.value,
    };
  }
}
