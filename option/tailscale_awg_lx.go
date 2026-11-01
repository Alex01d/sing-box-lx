package option

import (
	"errors"
	"reflect"

	"github.com/sagernet/sing-box/schema"
	"github.com/sagernet/sing/common/json"
)

// TailscaleAWGOptions configures only peer framing. Identity and peers remain
// owned by the Tailscale control plane.
type TailscaleAWGOptions struct {
	Version    int              `json:"version"`
	ProfileID  string           `json:"profile_id,omitempty"`
	Parameters AmneziaWGOptions `json:"parameters"`
}

func (o *TailscaleAWGOptions) UnmarshalJSON(data []byte) error {
	type plain TailscaleAWGOptions
	if err := json.UnmarshalDisallowUnknownFields(data, (*plain)(o)); err != nil {
		return errors.New("invalid awg: unknown field or invalid typed value")
	}
	return nil
}

func (o TailscaleAWGOptions) DescribeSchema(builder schema.Builder) (*schema.Node, error) {
	node := schema.StrictObject()
	if err := builder.FlattenStruct(node, reflect.TypeFor[TailscaleAWGOptions]()); err != nil {
		return nil, err
	}
	return node, nil
}
