package adapter

// TailscaleTransportStatus contains safe local configuration facts. It does
// not assert that any peer has authenticated or exchanged application data.
type TailscaleTransportStatus struct {
	ConfiguredMode     string
	AppliedMode        string
	ProfileID          string
	ProfileFingerprint string
	Applied            bool
	LastError          string
}
