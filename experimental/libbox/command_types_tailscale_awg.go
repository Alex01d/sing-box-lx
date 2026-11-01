package libbox

type TailscaleTransportStatus struct {
	ConfiguredMode     string
	AppliedMode        string
	ProfileID          string
	ProfileFingerprint string
	Applied            bool
	LastError          string
}
