import { Routes } from "@angular/router";
import { HomeComponent } from "./home.component";
import { TranscriptDetailComponent } from "./transcript-detail.component";

export const routes: Routes = [
  { path: "", component: HomeComponent },
  { path: "transcripts/:transcriptId", component: TranscriptDetailComponent },
  { path: "**", redirectTo: "" }
];
