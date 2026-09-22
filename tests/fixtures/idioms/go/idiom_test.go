package tests

import "testing"

func TestOne(t *testing.T) {
    t.Run("sub", func(t *testing.T) {
        require := t
        require.NoError(nil)
        require.Equal(1, 1)
        require.NotEqual(2, 3)
    })
}

func TestTwo(t *testing.T) {
    t.Run("sub", func(t *testing.T) {
        require := t
        require.NoError(nil)
        require.Equal(2, 2)
        require.NotEqual(3, 4)
    })
}
