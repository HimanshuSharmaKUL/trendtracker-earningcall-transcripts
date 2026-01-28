import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { HttpClient, HttpErrorResponse } from "@angular/common/http";
import { environment } from "../environments/environment";

type OrgFreq = {
  name: string;
  count: number;
};

type Orgs = {
  org_unique_count: number;
  org_freq: OrgFreq[];
};

type ViewTranscriptResponse = {
  transcript_id: string;
  company_id: string;
  company_name: string;
  fiscal_year: number;
  fiscal_quarter: number;
  transcript_text: string;
  org_data: Orgs;
};

@Component({
  selector: "app-transcript-detail",
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: "./transcript-detail.component.html",
  styleUrls: ["./transcript-detail.component.css"]
})
export class TranscriptDetailComponent {
  apiBaseUrl = environment.apiBaseUrl;
  viewLoading = false;
  viewError = "";
  viewResult: ViewTranscriptResponse | null = null;

  constructor(
    private http: HttpClient,
    private route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      const transcriptId = params.get("transcriptId");
      if (!transcriptId) {
        this.viewError = "Transcript id is missing.";
        this.viewResult = null;
        return;
      }
      this.fetchTranscript(transcriptId);
    });
  }

  private fetchTranscript(transcriptId: string): void {
    this.viewError = "";
    this.viewResult = null;
    this.viewLoading = true;

    this.http.get<ViewTranscriptResponse>(this.apiUrl(`/ingest/view/${transcriptId}`)).subscribe({
      next: (res) => {
        this.viewResult = res;
        this.viewLoading = false;
      },
      error: (err) => {
        this.viewError = this.readError(err);
        this.viewLoading = false;
      }
    });
  }

  private apiUrl(path: string): string {
    const base = this.apiBaseUrl.replace(/\/+$/, "");
    return `${base}${path}`;
  }

  private readError(err: HttpErrorResponse): string {
    if (err.error) {
      const detail = (err.error as { detail?: unknown }).detail;
      if (typeof detail === "string") {
        return detail;
      }
      if (Array.isArray(detail)) {
        const joined = detail
          .map((entry) => {
            if (typeof entry === "string") {
              return entry;
            }
            if (entry && typeof entry === "object" && "msg" in entry) {
              return String((entry as { msg?: unknown }).msg);
            }
            return JSON.stringify(entry);
          })
          .join(" | ");
        if (joined) {
          return joined;
        }
      }
      if (typeof err.error === "string") {
        return err.error;
      }
    }
    return err.message || "Request failed.";
  }
}
