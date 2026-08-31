import type { LatLngTuple } from "leaflet";

declare module "leaflet" {
  interface LeafletMouseEvent {
    latlng: {
      lat: number;
      lng: number;
    };
  }

  interface Map {
    setView(center: LatLngTuple, zoom?: number): this;
  }
}

declare module "react-leaflet" {
  interface MapContainerProps {
    center?: LatLngTuple;
    zoom?: number;
    scrollWheelZoom?: boolean;
  }

  interface TileLayerProps {
    attribution?: string;
    url?: string;
  }
}