import { whenReady, reactive } from "@odoo/owl";
import { mountComponent } from "@web/env";
import { Root } from "./root";
import "./services/store";

whenReady(() => mountComponent(Root, document.body));