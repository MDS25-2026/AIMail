package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"
)

// EmailPayload defines the structure of the JSON
// that n8n will send to this endpoint.
type EmailPayload struct {
	From    string `json:"from"`
	Subject string `json:"subject"`
	Body    string `json:"body"`
}

// webhookHandler is the function that runs every time
// n8n sends a POST request to /webhook/email.
func webhookHandler(w http.ResponseWriter, r *http.Request) {

	// Step 1: Only allow POST requests.
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Step 2: Read the raw request body.
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read request body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()
	// Step 2.5: Log the raw JSON received.
	log.Printf("Raw JSON received: %s", string(body))
	// Step 3: Parse the JSON body into our EmailPayload struct.
	var payload EmailPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		http.Error(w, "Invalid JSON payload", http.StatusBadRequest)
		return
	}

	// Step 4: Log the received email to the console (for now).
	// This is your confirmation that the pipeline works end to end.
	log.Printf("---NEW EMAIL RECEIVED---")
	log.Printf("Time received : %s", time.Now().Format(time.RFC3339))
	log.Printf("From          : %s", payload.From)
	log.Printf("Subject       : %s", payload.Subject)
	log.Printf("Body preview  : %.100s...", payload.Body)
	log.Printf("------------------------")

	// Step 5: Respond to n8n with 200 OK so it knows
	// the delivery was successful.
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{"status": "received"}`)
}

func main() {
	// Register the route and its handler function.
	http.HandleFunc("/webhook/email", webhookHandler)

	// Start the server on port 8081.
	// Current tunelling tool used: ngrok
	// in the ngrok terminal where this code is running, run command: ngrok http 8081
	port := ":8081"
	log.Printf("AiMail webhook listener running on port %s", port)
	log.Printf("Waiting for incoming emails from n8n...")

	if err := http.ListenAndServe(port, nil); err != nil {
		log.Fatalf("Server failed to start: %v", err)
	}
}