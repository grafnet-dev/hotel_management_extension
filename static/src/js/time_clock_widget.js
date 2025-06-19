/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class TimeClockWidget extends Component {
    static template = "hotel_management_extension.time_clock_widget";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.canvasRef = useRef("clockCanvas");
        this.clock = null;
        
        onMounted(() => {
            this.initClock();
        });
        
        onWillUnmount(() => {
            if (this.clock) {
                this.clock.destroy();
            }
        });
    }

    initClock() {
        const canvas = this.canvasRef.el;
        const updateCallback = this.props.readonly ? null : (newValue) => {
            if (this.props.update && typeof this.props.update === 'function') {
                this.props.update(newValue);
            }
        };
        
        this.clock = new InteractiveClock(
            canvas, 
            this.props.value || 14.0, 
            updateCallback, 
            this.props.readonly || false
        );
    }
}

class InteractiveClock {
    constructor(canvas, initialValue, onChangeCallback, readonly = false) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.centerX = canvas.width / 2;
        this.centerY = canvas.height / 2;
        this.radius = 120;
        this.onChangeCallback = onChangeCallback;
        this.readonly = readonly;
        
        // Temps initial
        this.timeFloat = initialValue;
        this.hours = Math.floor(this.timeFloat);
        this.minutes = Math.round((this.timeFloat - this.hours) * 60);
        
        this.isDragging = false;
        this.dragTarget = null;
        
        if (!this.readonly) {
            this.setupEventListeners();
        }
        this.draw();
    }
    
    setupEventListeners() {
        this.mouseDownHandler = (e) => this.onMouseDown(e);
        this.mouseMoveHandler = (e) => this.onMouseMove(e);
        this.mouseUpHandler = () => this.onMouseUp();
        
        this.canvas.addEventListener('mousedown', this.mouseDownHandler);
        this.canvas.addEventListener('mousemove', this.mouseMoveHandler);
        this.canvas.addEventListener('mouseup', this.mouseUpHandler);
        this.canvas.addEventListener('mouseleave', this.mouseUpHandler);
    }
    
    destroy() {
        this.canvas.removeEventListener('mousedown', this.mouseDownHandler);
        this.canvas.removeEventListener('mousemove', this.mouseMoveHandler);
        this.canvas.removeEventListener('mouseup', this.mouseUpHandler);
        this.canvas.removeEventListener('mouseleave', this.mouseUpHandler);
    }
    
    getMousePos(e) {
        const rect = this.canvas.getBoundingClientRect();
        return {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
    }
    
    getAngleFromMouse(mouseX, mouseY) {
        const dx = mouseX - this.centerX;
        const dy = mouseY - this.centerY;
        let angle = Math.atan2(dy, dx);
        angle = (angle + Math.PI * 2.5) % (Math.PI * 2);
        return angle;
    }
    
    isNearHand(mouseX, mouseY, handType) {
        const angle = handType === 'hour' ? 
            (this.hours % 12) * Math.PI / 6 : 
            this.minutes * Math.PI / 30;
        
        const handLength = handType === 'hour' ? this.radius * 0.5 : this.radius * 0.7;
        const handX = this.centerX + Math.cos(angle - Math.PI/2) * handLength;
        const handY = this.centerY + Math.sin(angle - Math.PI/2) * handLength;
        
        const distance = Math.sqrt((mouseX - handX) ** 2 + (mouseY - handY) ** 2);
        return distance < 20;
    }
    
    onMouseDown(e) {
        if (this.readonly) return;
        
        const mousePos = this.getMousePos(e);
        
        if (this.isNearHand(mousePos.x, mousePos.y, 'hour')) {
            this.isDragging = true;
            this.dragTarget = 'hour';
        } else if (this.isNearHand(mousePos.x, mousePos.y, 'minute')) {
            this.isDragging = true;
            this.dragTarget = 'minute';
        }
    }
    
    onMouseMove(e) {
        if (!this.isDragging) return;
        
        const mousePos = this.getMousePos(e);
        const angle = this.getAngleFromMouse(mousePos.x, mousePos.y);
        
        if (this.dragTarget === 'hour') {
            this.hours = Math.round(angle * 12 / (Math.PI * 2)) % 12;
            if (this.hours === 0) this.hours = 12;
        } else if (this.dragTarget === 'minute') {
            const minuteStep = 15;
            const totalMinutes = Math.round(angle * 60 / (Math.PI * 2));
            this.minutes = Math.round(totalMinutes / minuteStep) * minuteStep;
            if (this.minutes >= 60) this.minutes = 0;
        }
        
        this.updateTimeFloat();
        this.draw();
        
        // Notifier Odoo du changement seulement si la fonction existe
        if (this.onChangeCallback && typeof this.onChangeCallback === 'function') {
            this.onChangeCallback(this.timeFloat);
        }
    }
    
    onMouseUp() {
        this.isDragging = false;
        this.dragTarget = null;
    }
    
    updateTimeFloat() {
        this.timeFloat = this.hours + this.minutes / 60;
    }
    
    draw() {
        // Effacer le canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Dessiner le cercle principal
        this.ctx.beginPath();
        this.ctx.arc(this.centerX, this.centerY, this.radius, 0, Math.PI * 2);
        this.ctx.strokeStyle = '#875A7B'; // Couleur Odoo
        this.ctx.lineWidth = 3;
        this.ctx.stroke();
        this.ctx.fillStyle = '#fff';
        this.ctx.fill();
        
        // Dessiner les marques d'heures
        for (let i = 1; i <= 12; i++) {
            const angle = i * Math.PI / 6 - Math.PI / 2;
            const x1 = this.centerX + Math.cos(angle) * (this.radius - 20);
            const y1 = this.centerY + Math.sin(angle) * (this.radius - 20);
            const x2 = this.centerX + Math.cos(angle) * (this.radius - 10);
            const y2 = this.centerY + Math.sin(angle) * (this.radius - 10);
            
            this.ctx.beginPath();
            this.ctx.moveTo(x1, y1);
            this.ctx.lineTo(x2, y2);
            this.ctx.strokeStyle = '#666';
            this.ctx.lineWidth = 2;
            this.ctx.stroke();
            
            // Numéros
            const textX = this.centerX + Math.cos(angle) * (this.radius - 35);
            const textY = this.centerY + Math.sin(angle) * (this.radius - 35);
            this.ctx.fillStyle = '#333';
            this.ctx.font = '14px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText(i.toString(), textX, textY);
        }
        
        // Aiguille des heures
        const hourAngle = (this.hours % 12) * Math.PI / 6 - Math.PI / 2;
        const hourLength = this.radius * 0.5;
        this.ctx.beginPath();
        this.ctx.moveTo(this.centerX, this.centerY);
        this.ctx.lineTo(
            this.centerX + Math.cos(hourAngle) * hourLength,
            this.centerY + Math.sin(hourAngle) * hourLength
        );
        this.ctx.strokeStyle = this.dragTarget === 'hour' ? '#875A7B' : '#333';
        this.ctx.lineWidth = 6;
        this.ctx.lineCap = 'round';
        this.ctx.stroke();
        
        // Aiguille des minutes
        const minuteAngle = this.minutes * Math.PI / 30 - Math.PI / 2;
        const minuteLength = this.radius * 0.7;
        this.ctx.beginPath();
        this.ctx.moveTo(this.centerX, this.centerY);
        this.ctx.lineTo(
            this.centerX + Math.cos(minuteAngle) * minuteLength,
            this.centerY + Math.sin(minuteAngle) * minuteLength
        );
        this.ctx.strokeStyle = this.dragTarget === 'minute' ? '#17A2B8' : '#666';
        this.ctx.lineWidth = 4;
        this.ctx.lineCap = 'round';
        this.ctx.stroke();
        
        // Centre
        this.ctx.beginPath();
        this.ctx.arc(this.centerX, this.centerY, 8, 0, Math.PI * 2);
        this.ctx.fillStyle = '#333';
        this.ctx.fill();
    }
    
    setValue(value) {
        this.timeFloat = value || 14.0;
        this.hours = Math.floor(this.timeFloat);
        this.minutes = Math.round((this.timeFloat - this.hours) * 60);
        this.draw();
    }
}

registry.category("fields").add("time_clock_picker", {
    component: TimeClockWidget,
    supportedTypes: ["float"],
});